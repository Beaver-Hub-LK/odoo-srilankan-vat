from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    # ── New gazette-required fields ──────────────────────────────────────────

    l10n_lk_place_of_supply = fields.Char(
        string="Place of Supply",
        default=lambda self: self.env.company.city or "",
        help="Location from which the delivery of goods or services originates.",
    )
    l10n_lk_mode_of_payment = fields.Selection(
        selection=[
            ("cash", "Cash"),
            ("bank_transfer", "Bank Transfer"),
            ("cheque", "Cheque"),
            ("credit_card", "Credit Card"),
            ("debit_card", "Debit Card"),
            ("mobile_payment", "Mobile Payment"),
            ("online_payment", "Online Payment"),
        ],
        string="Mode of Payment",
        help="Form of payment used or expected for this invoice.",
    )
    l10n_lk_copy_count = fields.Integer(
        string="Copy Count",
        default=0,
        readonly=True,
        copy=False,
        help="Number of COPY ONLY reprints issued for this invoice.",
    )

    # ── Sequence helpers ─────────────────────────────────────────────────────

    def _is_l10n_lk_vat_sequence(self):
        """Return True when this move must use the gazette YYMMM_QQQQ_XXXXX format.

        Central guard - every sequence override and copy-reprint path branches on
        this check.  Extend here if future document types need gazette numbering.
        """
        self.ensure_one()
        return (
            self.company_id.l10n_lk_vat_enabled
            and self.move_type in ("out_invoice", "out_refund")
            and self.journal_id.type == "sale"
        )

    def _l10n_lk_vat_get_prefix(self):
        """Return the gazette prefix for the current invoice month: YYMMM_QQQQ_

        The trailing underscore is intentional - callers concatenate the numeric
        counter directly (e.g. prefix + '0' → '26JAN_HEAD_0').
        """
        self.ensure_one()
        move_date = self.date or self.invoice_date or fields.Date.context_today(self)
        year_month = move_date.strftime("%y%b").upper()  # e.g. '26JAN'
        unit_code = self.journal_id.l10n_lk_vat_unit_code or "HEAD"
        return f"{year_month}_{unit_code}_"

    # ── Computed fields ──────────────────────────────────────────────────────

    @api.depends("move_type", "company_id.l10n_lk_vat_enabled")
    def _compute_show_taxable_supply_date(self):
        # Base implementation sets the field to False for all moves; we then
        # override to True for LK VAT invoices so the Date of Delivery field
        # is always visible on the form and on the printed report.
        super()._compute_show_taxable_supply_date()
        for move in self:
            if move.company_id.l10n_lk_vat_enabled and move.is_invoice(include_receipts=False):
                move.show_taxable_supply_date = True
        return None

    # ── Sequence overrides ───────────────────────────────────────────────────

    def _get_last_sequence_domain(self, relaxed=False):
        """Enforce per-move-type sequence isolation for gazette sequences.

        Standard Odoo only separates credit notes when refund_sequence=True
        and debit notes when debit_sequence=True.  We always isolate them for
        LK VAT invoices so each document type has its own independent counter
        regardless of journal flags.

        Note: the WHERE clause fragments appended below use literal SQL values
        (not %s placeholders) - this matches the pattern of the parent method
        and is safe because all values are hardcoded Python strings, not user
        input.
        """
        where_string, param = super()._get_last_sequence_domain(relaxed)
        if self._is_l10n_lk_vat_sequence():
            if self.move_type == "out_refund":
                where_string += " AND move_type = 'out_refund' "
            else:
                where_string += " AND move_type != 'out_refund' "
            if self.debit_origin_id:
                where_string += " AND debit_origin_id IS NOT NULL "
            else:
                where_string += " AND debit_origin_id IS NULL "
        return where_string, param

    def _get_starting_sequence(self):
        """Return YYMMM_QQQQ_0 as the base sequence for gazette-format invoices."""
        if not self._is_l10n_lk_vat_sequence():
            return super()._get_starting_sequence()
        return self._l10n_lk_vat_get_prefix() + "0"

    def _sequence_matches_date(self):
        """For gazette sequences, verify the YYMMM_QQQQ_ prefix matches the invoice date.

        Note: invoices posted before this module was installed will have standard
        Odoo sequence numbers that do not match this prefix.  Those invoices will
        trigger a new sequence assignment on the next draft edit - this is expected
        behaviour and is documented in the module README.
        """
        if not self._is_l10n_lk_vat_sequence():
            return super()._sequence_matches_date()
        name = self.name
        if not name or name == "/":
            return True
        return name.startswith(self._l10n_lk_vat_get_prefix())

    def _get_next_sequence_format(self):
        """Bypass the mixin's regex-based format detection for gazette sequences.

        The gazette format YYMMM_QQQQ_XXXXX embeds the month abbreviation in the
        prefix.  The standard mixin locks the prefix to the last-used month, causing
        February invoices to carry a JAN prefix.  We fix this by computing the
        correct prefix from the invoice date and searching for the last number with
        that exact prefix.

        Implementation note: this method directly writes into the ``format_values``
        dict returned by ``_get_sequence_format_param``.  The keys ``seq``, ``year``,
        ``year_length``, and ``prefix2`` are internal to ``sequence.mixin`` and may
        change across Odoo versions.  The dict is validated below with an assertion
        so a mismatch surfaces immediately on the first invoice of a new deployment
        rather than silently producing a wrong sequence number.
        """
        if not self._is_l10n_lk_vat_sequence():
            return super()._get_next_sequence_format()

        prefix = self._l10n_lk_vat_get_prefix()  # e.g. '26FEB_HEAD_'
        base_sequence = prefix + "0"  # e.g. '26FEB_HEAD_0'

        # Scope the search to the exact YYMMM_QQQQ_ prefix so each month+unit
        # combination gets its own independent counter.
        last_sequence = self._get_last_sequence(with_prefix=prefix)

        format_string, format_values = self._get_sequence_format_param(
            last_sequence if last_sequence else base_sequence
        )

        if not last_sequence:
            # Defensive assertion: if the mixin's regex did not parse the gazette
            # format into the expected keys, fail loudly here rather than silently
            # producing a malformed sequence number.
            assert "prefix2" in format_values, (
                f"sequence.mixin did not parse '{base_sequence}' into expected "
                "format_values keys. Check _get_sequence_format_param for changes "
                "in this Odoo version."
            )
            # No previous sequence for this YYMMM_QQQQ - start counter at 0;
            # _locked_increment will increment to 1 before writing.
            format_values["seq"] = 0
            move_date = self.date or self.invoice_date or fields.Date.context_today(self)
            if format_values.get("year_length"):
                format_values["year"] = self._truncate_year_to_length(move_date.year, format_values["year_length"])
            unit_code = self.journal_id.l10n_lk_vat_unit_code or "HEAD"
            format_values["prefix2"] = move_date.strftime("%b").upper() + "_" + unit_code + "_"

        return format_string, format_values

    # ── Print action ─────────────────────────────────────────────────────────

    def action_print_pdf(self):
        """Use the dedicated VAT report action for gazette-format invoices.

        Two reasons to bypass super() for LK VAT invoices:

        1. Paper format: ``action_report_vat_invoice`` carries the LK-specific A4
           paper format with 10 mm margins.  Routing through ``account.account_invoices``
           would apply that action's (global) paper format to non-LK companies as a
           side-effect.

        2. Layout configurator: Odoo 19 redirects admin users to the document-layout
           wizard when ``company.external_report_layout_id`` is unset.  Our gazette
           template does not use ``web.external_layout``, so the wizard is irrelevant
           and would block printing.  ``config=False`` skips it explicitly.

        Note: ``account.move.send._get_default_pdf_report_id`` is a private method
        (prefixed with _) and may be renamed in future Odoo versions.  If this
        breaks on upgrade, fall back to:
            self.env.ref('l10n_lk_vat.action_report_vat_invoice').report_action(self)
        """
        self.ensure_one()
        if self._is_l10n_lk_vat_sequence():
            return self.env.ref("l10n_lk_vat.action_report_vat_invoice").report_action(
                self,
                config=False,
            )
        return super().action_print_pdf()

    # ── Copy count increment (called from copy wizard) ───────────────────────

    def l10n_lk_increment_copy_count(self, reason):
        """Increment the COPY ONLY reprint counter and log to the chatter.

        Guards are intentionally enforced here (not only in the wizard) because
        this method is a public ORM method callable via XML-RPC/JSON-RPC.
        """
        self.ensure_one()
        if not self._is_l10n_lk_vat_sequence():
            raise UserError(_("COPY ONLY reprints are only available for Sri Lanka VAT invoices."))
        if self.state != "posted":
            raise UserError(_("A COPY ONLY reprint can only be issued for a confirmed (posted) invoice."))
        self.write({"l10n_lk_copy_count": self.l10n_lk_copy_count + 1})
        self.message_post(
            body=_(
                "COPY ONLY reprint #%(count)s generated by %(user)s. Reason: %(reason)s",
                count=self.l10n_lk_copy_count,
                user=self.env.user.name,
                reason=reason,
            )
        )
