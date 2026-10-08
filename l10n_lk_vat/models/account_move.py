import re

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import SQL

# Gazette 2481/22 clause 4.1.a.ii: "MMM" is the first three characters of the
# month name in uppercase. Hard-coded so the serial never depends on the
# server locale (strftime('%b') is locale dependent).
L10N_LK_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")

# Key of the per-transaction dict (in cr.precommit.data) holding the print
# mode decided for each move by ir.actions.report._pre_render_qweb_pdf.
# It lives server-side only, so a client cannot forge it through the
# report URL context (unlike a context key).
L10N_LK_PRINT_MODES_KEY = "l10n_lk_vat.print_modes"


class AccountMove(models.Model):
    _inherit = "account.move"

    # ── Gazette-required / optional fields ───────────────────────────────────

    l10n_lk_place_of_supply = fields.Char(
        string="Place of Supply",
        default=lambda self: self.env.company.city or "",
        help="Optional (gazette 2481/22 clause 4.1.c): the location from which the delivery of "
        "goods or services originates, when it differs from where the invoice is issued. "
        "Printed only when set.",
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
        help="Number of COPY ONLY reprints issued for this invoice (each one is logged in the chatter).",
    )
    l10n_lk_copy_pending = fields.Boolean(
        string="COPY ONLY Print Pending",
        readonly=True,
        copy=False,
        help="Technical: set by the Print Copy wizard (which already logged the reason) and "
        "consumed by the next COPY ONLY render, so that render is not logged twice.",
    )
    l10n_lk_print_as_tax_invoice = fields.Boolean(
        string="Print as Tax Invoice",
        compute="_compute_l10n_lk_print_as_tax_invoice",
        store=True,
        readonly=False,
        precompute=True,
        help="On: the document prints as a gazette TAX INVOICE / TAX CREDIT NOTE / TAX DEBIT NOTE "
        "with the purchaser's TIN.\n"
        "Off: the same gazette-style layout prints titled INVOICE / CREDIT NOTE / DEBIT NOTE "
        "without the purchaser TIN (customers that are not VAT registered).\n"
        "Defaults from the customer: on when the customer has a Tax ID (TIN), off otherwise. "
        "Does not affect the serial number.",
    )
    l10n_lk_vat_exempt_warning = fields.Text(
        string="Tax Invoice Exempt Lines Warning",
        compute="_compute_l10n_lk_vat_exempt_warning",
        help="Gazette 2481/22 clause 4.2: a Tax Invoice shall exclusively include supplies " "subject to VAT.",
    )

    # ── Original print lock (audit) ──────────────────────────────────────────
    l10n_lk_original_printed = fields.Boolean(
        string="Original Printed",
        readonly=True,
        copy=False,
        tracking=True,
        help="Set when the ORIGINAL of this posted document was first rendered as PDF "
        "(Print button, Print menu, Send & Print or e-mail). Every later render is a COPY ONLY.",
    )
    l10n_lk_original_printed_date = fields.Datetime(
        string="Original Printed On",
        readonly=True,
        copy=False,
        tracking=True,
    )
    l10n_lk_original_printed_by = fields.Many2one(
        comodel_name="res.users",
        string="Original Printed By",
        readonly=True,
        copy=False,
        tracking=True,
    )

    # ── Sequence helpers ─────────────────────────────────────────────────────

    def _is_l10n_lk_vat_sequence(self):
        """Return True when this move must use the gazette YYMMM_QQQQ_XXXXX format.

        Central guard - every sequence override, print route and copy-reprint
        path branches on this check.
        """
        self.ensure_one()
        return bool(
            self.company_id.l10n_lk_vat_enabled
            and self.move_type in ("out_invoice", "out_refund")
            and self.journal_id.type == "sale"
        )

    def _l10n_lk_vat_move_date(self):
        return self.date or self.invoice_date or fields.Date.context_today(self)

    def _l10n_lk_vat_unit_code(self):
        return self.journal_id.l10n_lk_vat_unit_code or "HEAD"

    def _l10n_lk_vat_get_prefix(self):
        """Return the gazette prefix for the current invoice month: YYMMM_QQQQ_

        The trailing underscore is intentional - callers concatenate the numeric
        counter directly (e.g. prefix + '1' → '26JUL_BR03_1').
        """
        self.ensure_one()
        move_date = self._l10n_lk_vat_move_date()
        year_month = "%02d%s" % (move_date.year % 100, L10N_LK_MONTHS[move_date.month - 1])
        return f"{year_month}_{self._l10n_lk_vat_unit_code()}_"

    def _l10n_lk_vat_sequence_reset(self):
        return self.journal_id.l10n_lk_vat_sequence_reset or "continuous"

    def _l10n_lk_vat_counter_period(self):
        """Identify the counter period of this move under the journal's reset policy.

        continuous → one counter forever, yearly → one per calendar year,
        monthly → one per month (i.e. per YYMMM prefix).
        """
        self.ensure_one()
        reset = self._l10n_lk_vat_sequence_reset()
        prefix = self._l10n_lk_vat_get_prefix()
        if reset == "monthly":
            return prefix[:5]
        if reset == "yearly":
            return prefix[:2]
        return "all"

    def _l10n_lk_vat_counter_prefix_regex(self):
        """POSIX regex matching every sequence_prefix that shares this move's counter."""
        self.ensure_one()
        reset = self._l10n_lk_vat_sequence_reset()
        prefix = self._l10n_lk_vat_get_prefix()
        unit = re.escape(self._l10n_lk_vat_unit_code())
        if reset == "monthly":
            head = prefix[:5]
        elif reset == "yearly":
            head = prefix[:2] + "[A-Z]{3}"
        else:
            head = "[0-9]{2}[A-Z]{3}"
        return f"^{head}_{unit}_$"

    def _l10n_lk_vat_last_number(self):
        """Highest gazette serial (XXXXX) already used by this move's counter.

        The counter is shared by invoices, credit notes and debit notes of the
        same journal + unit code, and spans the months/years allowed by the
        journal's reset policy. Any move holding such a name is considered
        (posted, or reset to draft after posting) so a number is never reused.
        """
        self.ensure_one()
        self.flush_model(["name", "journal_id", "sequence_prefix", "sequence_number"])
        self.env.cr.execute(
            SQL(
                """
                SELECT sequence_number
                  FROM account_move
                 WHERE journal_id = %(journal_id)s
                   AND id != %(id)s
                   AND name IS NOT NULL AND name != '/'
                   AND sequence_prefix ~ %(regex)s
              ORDER BY sequence_number DESC
                 LIMIT 1
                """,
                journal_id=self.journal_id.id,
                id=self._origin.id or 0,
                regex=self._l10n_lk_vat_counter_prefix_regex(),
            )
        )
        row = self.env.cr.fetchone()
        return row[0] if row and row[0] else 0

    # ── Computed fields ──────────────────────────────────────────────────────

    @api.depends("move_type", "company_id.l10n_lk_vat_enabled")
    def _compute_show_taxable_supply_date(self):
        # Base implementation sets the field to False for all moves; we then
        # override to True for LK VAT invoices so the Date of Supply field
        # is always visible on the form and on the printed report.
        super()._compute_show_taxable_supply_date()
        for move in self:
            if move.company_id.l10n_lk_vat_enabled and move.is_invoice(include_receipts=False):
                move.show_taxable_supply_date = True
        return None

    @api.depends("partner_id")
    def _compute_l10n_lk_print_as_tax_invoice(self):
        """Default from the customer: Tax Invoice only for VAT-registered buyers.

        Only draft documents follow the customer; once posted (or cancelled)
        the value is frozen so a later change on the partner's Tax ID can never
        silently re-title an issued document.
        """
        for move in self:
            if move._origin.id and move.state in ("posted", "cancel"):
                move.l10n_lk_print_as_tax_invoice = move._origin.l10n_lk_print_as_tax_invoice
                continue
            partner = move.partner_id.commercial_partner_id
            move.l10n_lk_print_as_tax_invoice = bool(partner.vat)

    def _l10n_lk_vat_exempt_lines(self):
        """Product lines of a Tax Invoice that carry no VAT (no tax / 0% / exempt)."""
        self.ensure_one()
        if not (self._is_l10n_lk_vat_sequence() and self.l10n_lk_print_as_tax_invoice):
            return self.env["account.move.line"]
        return self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
            and not any(tax.amount for tax in line.tax_ids.flatten_taxes_hierarchy())
        )

    @api.depends(
        "l10n_lk_print_as_tax_invoice",
        "move_type",
        "journal_id",
        "company_id.l10n_lk_vat_enabled",
        "invoice_line_ids.tax_ids",
        "invoice_line_ids.display_type",
        "invoice_line_ids.name",
    )
    def _compute_l10n_lk_vat_exempt_warning(self):
        for move in self:
            lines = move._l10n_lk_vat_exempt_lines()
            if not lines:
                move.l10n_lk_vat_exempt_warning = False
                continue
            names = ", ".join((line.name or line.product_id.display_name or "?").splitlines()[0] for line in lines[:5])
            if len(lines) > 5:
                names += ", ..."
            move.l10n_lk_vat_exempt_warning = _(
                "This document is printed as a Tax Invoice but %(count)s line(s) carry no VAT "
                "(no tax, 0%% or exempt): %(names)s. Gazette 2481/22 clause 4.2 requires a Tax "
                "Invoice to include only VAT-taxable supplies - issue exempt supplies on a separate "
                "(non-tax) invoice unless they are an integral part of the taxable supply.",
                count=len(lines),
                names=names,
            )

    # ── Posting guard (gazette 4.2) ──────────────────────────────────────────

    def _post(self, soft=True):
        for move in self:
            if (
                move.company_id.l10n_lk_vat_block_exempt_on_tax_invoice
                and move.is_invoice(include_receipts=False)
                and move._l10n_lk_vat_exempt_lines()
            ):
                raise UserError(
                    _(
                        "%(doc)s cannot be posted as a Tax Invoice: %(warning)s\n\n"
                        "Remove the exempt lines, add VAT to them, or switch off "
                        "'Print as Tax Invoice'.",
                        doc=move.display_name,
                        warning=move.l10n_lk_vat_exempt_warning,
                    )
                )
        return super()._post(soft=soft)

    # ── Sequence overrides ───────────────────────────────────────────────────

    def _get_starting_sequence(self):
        """Return YYMMM_QQQQ_0 as the base sequence for gazette-format invoices."""
        if not self._is_l10n_lk_vat_sequence():
            return super()._get_starting_sequence()
        return self._l10n_lk_vat_get_prefix() + "0"

    def _sequence_matches_date(self):
        """For gazette sequences, verify the YYMMM_QQQQ_ prefix matches the invoice date."""
        if not self._is_l10n_lk_vat_sequence():
            return super()._sequence_matches_date()
        name = self.name
        if not name or name == "/":
            return True
        return name.startswith(self._l10n_lk_vat_get_prefix())

    def _get_next_sequence_format(self):
        """Build the gazette YYMMM_QQQQ_XXXXX format directly, bypassing the mixin's regex.

        The mixin infers the format by regex-parsing the previous number. That
        breaks on the gazette layout: the month is alphabetic (so the prefix
        would stay locked to the last-used month), and a unit code ending in
        digits that look like a month (e.g. "BR03", the gazette's own example)
        is parsed as ``{prefix2}{month}``, producing "26AUG_BR03_03_1".

        Instead the prefix is always computed from the invoice date and unit
        code, and the counter continues from the highest number of the
        journal's counter period (see ``l10n_lk_vat_sequence_reset``).
        """
        if not self._is_l10n_lk_vat_sequence():
            return super()._get_next_sequence_format()
        prefix = self._l10n_lk_vat_get_prefix()  # e.g. '26FEB_BR03_'
        # _locked_increment adds 1 before writing, so start from the last used number.
        return "{prefix1}{seq:d}", {"prefix1": prefix, "seq": self._l10n_lk_vat_last_number()}

    def _locked_increment(self, format_string, format_values):
        """Concurrency-safe increment for continuous / yearly gazette counters.

        The mixin locks a number through the (name, journal_id) unique index
        and caches the counter under ``format_string.format(seq=0)`` - i.e. per
        YYMMM prefix. That is exactly right for the monthly policy (delegated
        to super), but not when one counter spans several prefixes:

        * the cache key changes every month, so a back-dated invoice posted in
          the same transaction would reuse a stale per-month counter, and
        * "26SEP_HEAD_7" and "26OCT_HEAD_7" never collide on the unique index,
          so two concurrent transactions could both issue number 7.

        For continuous / yearly counters we therefore (1) serialise number
        assignment per journal by updating the journal row (a concurrent
        poster gets a serialization failure and Odoo retries its request) and
        (2) cache the counter under a key that identifies the whole counter
        (journal + unit + period), not the month.
        """
        if len(self) != 1 or not self._is_l10n_lk_vat_sequence() or self._l10n_lk_vat_sequence_reset() == "monthly":
            return super()._locked_increment(format_string, format_values)

        cache = self._get_sequence_cache()
        seq = format_values.pop("seq")
        cache_key = (
            "l10n_lk_vat",
            self.journal_id.id,
            self._l10n_lk_vat_unit_code(),
            self._l10n_lk_vat_counter_period(),
        )
        if cache_key in cache:
            cache[cache_key] += 1
            return format_string.format(**format_values, seq=cache[cache_key])

        self.flush_recordset()
        self.env.cr.execute(SQL("UPDATE account_journal SET write_date = write_date WHERE id = %s", self.journal_id.id))
        # Re-read under the lock (cheap, and guards against a caller passing a stale seq).
        seq = max(seq, self._l10n_lk_vat_last_number())
        with self.env.cr.savepoint(flush=False) as sp:
            while True:
                seq += 1
                sequence = format_string.format(**format_values, seq=seq)
                try:
                    self.env.cr.execute(
                        SQL(
                            "UPDATE %(table)s SET %(fname)s = %(sequence)s WHERE id = %(id)s",
                            table=SQL.identifier(self._table),
                            fname=SQL.identifier(self._sequence_field),
                            sequence=sequence,
                            id=self.id,
                        ),
                        log_exceptions=False,
                    )
                    cache[cache_key] = seq
                    return sequence
                except Exception as e:  # noqa: BLE001 - unique violation → try next number
                    if getattr(e, "pgcode", None) not in ("23505", "23P01"):
                        raise
                    sp.rollback()

    # ── Print routing ────────────────────────────────────────────────────────

    def _l10n_lk_vat_doc_title(self):
        """Printed document title (gazette 1.1: TAX INVOICE in bold)."""
        self.ensure_one()
        is_debit = self.move_type == "out_invoice" and bool(self.debit_origin_id)
        if self.move_type == "out_refund":
            base = "CREDIT NOTE"
        elif is_debit:
            base = "DEBIT NOTE"
        else:
            base = "INVOICE"
        return ("TAX " + base) if self.l10n_lk_print_as_tax_invoice else base

    def _l10n_lk_vat_copy_wizard_action(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("l10n_lk_vat.action_l10n_lk_copy_invoice")
        action["context"] = {"default_move_id": self.id}
        return action

    def action_print_pdf(self):
        """Gazette-style PDF for every LK VAT sales document.

        * Tax Invoice or plain Invoice: same gazette layout, only the title,
          the purchaser TIN row and the number label differ (see template).
        * Once the ORIGINAL has been printed, this button no longer prints:
          it opens the Print Copy wizard (reason required, logged).

        ``config=False`` skips Odoo 19's document-layout configurator, which
        is irrelevant for our template (it does not use web.external_layout).
        """
        self.ensure_one()
        if self._is_l10n_lk_vat_sequence():
            if self.state == "posted" and self.l10n_lk_original_printed:
                return self._l10n_lk_vat_copy_wizard_action()
            return self.env.ref("l10n_lk_vat.action_report_vat_invoice").report_action(self, config=False)
        return super().action_print_pdf()

    # ── Print-mode bookkeeping (called from ir.actions.report) ───────────────

    def _l10n_lk_vat_print_mode(self):
        """Return 'original', 'copy' or 'preview' for the document being rendered."""
        self.ensure_one()
        modes = self.env.cr.precommit.data.get(L10N_LK_PRINT_MODES_KEY) or {}
        if self.id in modes:
            return modes[self.id]
        # Rendered outside the PDF chokepoint (e.g. HTML preview): never let it
        # look like a second original.
        if self.state == "posted" and self.l10n_lk_original_printed:
            return "copy"
        return "preview"

    def _l10n_lk_vat_register_print(self, path, copy_requested=False):
        """Decide (and record) whether this render is the ORIGINAL or a COPY.

        Returns {move_id: 'original' | 'copy' | 'preview'}.
        """
        modes = {}
        user = self.env.user
        for move in self:
            if move.state != "posted" or not move._is_l10n_lk_vat_sequence():
                modes[move.id] = "preview"
                continue
            move_sudo = move.sudo()
            if copy_requested and move.l10n_lk_copy_pending:
                # Print Copy wizard: reason + counter already logged there.
                move_sudo.write({"l10n_lk_copy_pending": False})
                modes[move.id] = "copy"
            elif not move.l10n_lk_original_printed:
                move_sudo.write(
                    {
                        "l10n_lk_original_printed": True,
                        "l10n_lk_original_printed_date": fields.Datetime.now(),
                        "l10n_lk_original_printed_by": user.id,
                    }
                )
                move_sudo.message_post(body=_("ORIGINAL printed via %(path)s by %(user)s.", path=path, user=user.name))
                modes[move.id] = "original"
            else:
                move_sudo.write({"l10n_lk_copy_count": move.l10n_lk_copy_count + 1})
                move_sudo.message_post(
                    body=_(
                        "Reprint as COPY ONLY via %(path)s by %(user)s (COPY ONLY reprint #%(count)s).",
                        path=path,
                        user=user.name,
                        count=move_sudo.l10n_lk_copy_count,
                    )
                )
                modes[move.id] = "copy"
        # Fail fast inside read-only request cursors (Odoo retries read/write).
        self.flush_recordset()
        return modes

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
        self.sudo().write({"l10n_lk_copy_count": self.l10n_lk_copy_count + 1, "l10n_lk_copy_pending": True})
        self.sudo().message_post(
            body=_(
                "COPY ONLY reprint #%(count)s generated via Print Copy wizard by %(user)s. Reason: %(reason)s",
                count=self.l10n_lk_copy_count,
                user=self.env.user.name,
                reason=reason,
            )
        )

    def l10n_lk_reset_original_print(self, reason):
        """Accounting managers only: clear the ORIGINAL printed lock after a genuine misprint."""
        self.ensure_one()
        if not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(_("Only accounting managers can reset the original print of an invoice."))
        if not (reason or "").strip():
            raise UserError(_("A reason is required to reset the original print."))
        if not self.l10n_lk_original_printed:
            raise UserError(_("The original of this document has not been printed yet."))
        previous = Markup("%s / %s") % (
            self.l10n_lk_original_printed_by.name or "-",
            fields.Datetime.to_string(self.l10n_lk_original_printed_date) or "-",
        )
        self.sudo().write(
            {
                "l10n_lk_original_printed": False,
                "l10n_lk_original_printed_date": False,
                "l10n_lk_original_printed_by": False,
            }
        )
        self.sudo().message_post(
            body=_(
                "Original print RESET by %(user)s (previous original: %(previous)s). Reason: %(reason)s",
                user=self.env.user.name,
                previous=previous,
                reason=reason,
            )
        )
