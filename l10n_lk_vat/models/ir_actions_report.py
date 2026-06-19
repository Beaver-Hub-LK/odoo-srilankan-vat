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
