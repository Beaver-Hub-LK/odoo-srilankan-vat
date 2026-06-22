from odoo import api, models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    @api.model
    def _build_wkhtmltopdf_args(
        self, paperformat_id, landscape, specific_paperformat_args=None, set_viewport_size=False
    ):
        """Force UTF-8 encoding and support left/right margin overrides.

        Odoo's base _build_wkhtmltopdf_args reads --margin-left and --margin-right
        directly from paperformat_id with no override hook in specific_paperformat_args.
        We post-process the command list here to replace those values when
        data-report-margin-left / data-report-margin-right are present.
        """
        command_args = super()._build_wkhtmltopdf_args(
            paperformat_id,
            landscape,
            specific_paperformat_args=specific_paperformat_args,
            set_viewport_size=set_viewport_size,
        )

        # Guard against double-insertion if another module or future Odoo version
        # already adds --encoding utf-8.
        if "--encoding" not in command_args:
            command_args.extend(["--encoding", "utf-8"])

        if specific_paperformat_args:
            for flag, key in (
                ("--margin-left", "data-report-margin-left"),
                ("--margin-right", "data-report-margin-right"),
            ):
                if key in specific_paperformat_args:
                    try:
                        idx = command_args.index(flag)
                        command_args[idx + 1] = str(specific_paperformat_args[key])
                    except ValueError:
                        command_args.extend([flag, str(specific_paperformat_args[key])])

        return command_args

    def _pre_render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """Redirect Odoo's stock invoice report to the gazette Tax Invoice.

        This is the lowest-level method common to every PDF entry point
        except the dedicated in-form Print button (which calls
        action_report_vat_invoice directly and never reaches this method
        at all). The cog-wheel Print menu reaches here via the
        /report/download controller -> _render_qweb_pdf -> here, using the
        report_name STRING "account.report_invoice_with_payments" - it
        never calls report_action() despite that name suggesting otherwise.
        account.move.send._prepare_invoice_pdf_report (the Send & Print
        wizard) calls this method directly with the same string. Both
        bypassed our per-invoice "Print as Tax Invoice" toggle entirely
        until this override - this is the single chokepoint that actually
        catches them.
        """
        if self._is_default_invoice_report(report_ref) and res_ids:
            moves = self._l10n_lk_vat_resolve_moves(res_ids)
            if moves and all(move._is_l10n_lk_vat_sequence() and move.l10n_lk_print_as_tax_invoice for move in moves):
                return super()._pre_render_qweb_pdf("l10n_lk_vat.report_vat_invoice", res_ids=res_ids, data=data)
        return super()._pre_render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """Block fraudulent COPY ONLY stamps injected via the rendering context.

        The 'COPY ONLY' stamp in the QWeb template is driven by the
        l10n_lk_vat_copy_mode context key.  Without this guard, any user with
        invoice-print access could craft a report URL carrying that key and obtain
        a COPY-stamped PDF without going through the wizard, bypassing the audit
        trail and gazette compliance requirement.

        Guard: if copy_mode is requested but none of the target invoices has had
        its copy counter incremented (i.e. the wizard was never called for them),
        strip the context flag so no stamp is rendered.  The wizard always
        increments l10n_lk_copy_count before returning the print action, so
        legitimate copy prints always satisfy this check.
        """
        if self.env.context.get("l10n_lk_vat_copy_mode") and self._is_lk_vat_report(report_ref) and res_ids:
            ids = [res_ids] if isinstance(res_ids, int) else list(res_ids)
            moves = self.env["account.move"].browse(ids)
            if not all(m.l10n_lk_copy_count > 0 for m in moves):
                return self.with_context(l10n_lk_vat_copy_mode=False)._render_qweb_pdf(
                    report_ref, res_ids=res_ids, data=data
                )
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

    def _run_wkhtmltopdf(
        self,
        bodies,
        report_ref=False,
        header=None,
        footer=None,
        landscape=False,
        specific_paperformat_args=None,
        set_viewport_size=False,
    ):
        """Fix all margins and strip the empty header for our gazette invoice."""
        if self._is_lk_vat_report(report_ref):
            header = None
            if specific_paperformat_args is None:
                specific_paperformat_args = {}
            specific_paperformat_args.setdefault("data-report-margin-top", "10")
            specific_paperformat_args.setdefault("data-report-margin-bottom", "10")
            specific_paperformat_args.setdefault("data-report-margin-left", "10")
            specific_paperformat_args.setdefault("data-report-margin-right", "10")
            specific_paperformat_args.setdefault("data-report-header-spacing", "0")
            specific_paperformat_args.setdefault("data-report-dpi", "96")
        return super()._run_wkhtmltopdf(
            bodies,
            report_ref=report_ref,
            header=header,
            footer=footer,
            landscape=landscape,
            specific_paperformat_args=specific_paperformat_args,
            set_viewport_size=set_viewport_size,
        )

    def _is_lk_vat_report(self, report_ref):
        """Return True when report_ref refers to our gazette invoice report."""
        if isinstance(report_ref, str):
            return report_ref == "l10n_lk_vat.report_vat_invoice"
        if isinstance(report_ref, int):
            return False
        if report_ref and hasattr(report_ref, "report_name"):
            return report_ref.report_name == "l10n_lk_vat.report_vat_invoice"
        return False

    def _is_default_invoice_report(self, report_ref):
        """Return True when report_ref refers to Odoo's stock invoice report."""
        if isinstance(report_ref, str):
            return report_ref == "account.report_invoice_with_payments"
        if isinstance(report_ref, int):
            return False
        if report_ref and hasattr(report_ref, "report_name"):
            return report_ref.report_name == "account.report_invoice_with_payments"
        return False

    def _is_default_invoice_action(self):
        """Return True when self is exactly the core "Invoice PDF" action."""
        default_invoice_action = self.env.ref("account.account_invoices", raise_if_not_found=False)
        return bool(default_invoice_action) and self.id == default_invoice_action.id

    def report_action(self, docids, data=None, config=True):
        """Redirect the stock "Invoice PDF" action to the gazette Tax Invoice
        for any caller that explicitly invokes report_action() on it.

        Note: neither the cog-wheel Print menu nor account.move.send reach
        this method - they call _pre_render_qweb_pdf directly/indirectly
        with a report_name string, never report_action(). See that
        override above for the chokepoint that actually covers them. This
        one is a defensive backstop for any other code (ours or a third
        party module) that builds an action via report_action() the way
        account.move.action_print_pdf's super() fallback does.

        config is forced to False on the redirect target regardless of what
        the caller passed in: our gazette template does not use
        web.external_layout, so the "configure your document layout" wizard
        Odoo offers admins when company.external_report_layout_id is unset
        is irrelevant for it and would otherwise block printing.
        """
        if docids and self._is_default_invoice_action():
            moves = self._l10n_lk_vat_resolve_moves(docids)
            if moves and all(move._is_l10n_lk_vat_sequence() and move.l10n_lk_print_as_tax_invoice for move in moves):
                return self.env.ref("l10n_lk_vat.action_report_vat_invoice").report_action(
                    docids, data=data, config=False
                )
        return super().report_action(docids, data=data, config=config)

    def _l10n_lk_vat_resolve_moves(self, docids):
        """Normalize docids (recordset/int/list) into an account.move recordset."""
        if isinstance(docids, models.Model):
            ids = docids.ids
        elif isinstance(docids, int):
            ids = [docids]
        else:
            ids = list(docids)
        return self.env["account.move"].browse(ids).exists()
