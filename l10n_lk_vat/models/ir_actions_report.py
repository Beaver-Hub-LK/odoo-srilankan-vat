from collections import OrderedDict

from odoo import api, models
from odoo.http import request

from .account_move import L10N_LK_PRINT_MODES_KEY


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

    def _l10n_lk_vat_qualifies(self, moves):
        """All moves are LK VAT sales documents → gazette-style layout.

        Both Tax Invoices and plain (non-VAT buyer) Invoices use the gazette
        design; ``l10n_lk_print_as_tax_invoice`` only changes the title and
        the purchaser TIN row inside the template.
        """
        return bool(moves) and all(move._is_l10n_lk_vat_sequence() for move in moves)

    def _pre_render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """Single chokepoint for every PDF of an LK VAT sales document.

        Reached by the in-form Print button (our report via /report/download),
        the cog-wheel Print menu (account.report_invoice_with_payments via
        /report/download -> _render_qweb_pdf), the Send & Print wizard
        (account.move.send calls this method directly) and e-mail templates.

        1. Redirects Odoo's stock invoice report to the gazette template.
        2. Decides, per posted document, whether this render is the ORIGINAL
           (first PDF ever) or a COPY ONLY (every later render), records it
           (fields + chatter) and hands the decision to the template through
           a server-side, per-transaction dict - never through the context,
           which a user can forge in the report URL.
        """
        if res_ids and (self._is_default_invoice_report(report_ref) or self._is_lk_vat_report(report_ref)):
            moves = self._l10n_lk_vat_resolve_moves(res_ids)
            if self._l10n_lk_vat_qualifies(moves):
                if data and data.get("proforma"):
                    modes = {move.id: "preview" for move in moves}
                else:
                    path = self.env.context.get("l10n_lk_vat_print_path") or "Send & Print"
                    copy_requested = bool(self.env.context.get("l10n_lk_vat_copy_mode"))
                    modes = moves._l10n_lk_vat_register_print(path, copy_requested=copy_requested)
                store = self.env.cr.precommit.data.setdefault(L10N_LK_PRINT_MODES_KEY, {})
                store.update(modes)
                try:
                    return super(IrActionsReport, self.with_context(l10n_lk_vat_copy_mode=False))._pre_render_qweb_pdf(
                        "l10n_lk_vat.report_vat_invoice", res_ids=res_ids, data=data
                    )
                finally:
                    for move_id in modes:
                        store.pop(move_id, None)
        return super()._pre_render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        """Render gazette documents one record at a time.

        The gazette template prints one or more copies per document, so the
        number of pages never maps 1:1 to records and it has no outline
        headings; the stock splitter would then return a single unsplit PDF
        and Send & Print (which needs one PDF per invoice) would fail.
        """
        if self._is_lk_vat_report(report_ref) and res_ids and len(res_ids) > 1 and len(set(res_ids)) == len(res_ids):
            collected_streams = OrderedDict()
            for res_id in res_ids:
                collected_streams.update(
                    super()._render_qweb_pdf_prepare_streams(report_ref, dict(data or {}), res_ids=[res_id])
                )
            return collected_streams
        return super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """Tag the render with the user-facing entry point, for the audit log.

        The value is always overwritten here, so a context forged in the
        report URL cannot spoof it. The COPY ONLY decision itself is taken in
        _pre_render_qweb_pdf from server-side state only: a forged
        ``l10n_lk_vat_copy_mode`` is ignored unless the Print Copy wizard has
        just armed ``l10n_lk_copy_pending`` on the document.
        """
        if self._is_lk_vat_report(report_ref) or self._is_default_invoice_report(report_ref):
            if self.env.context.get("l10n_lk_vat_copy_mode"):
                path = "Print Copy wizard"
            elif request and request.httprequest.path.startswith("/report/"):
                path = "Print button" if self._is_lk_vat_report(report_ref) else "Print menu"
            else:
                path = "e-mail / API"
            self = self.with_context(l10n_lk_vat_print_path=path)
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
            if self._l10n_lk_vat_qualifies(moves):
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
