from odoo.tests import tagged

from .common import L10nLkVatCommon


@tagged("post_install", "-at_install")
class TestL10nLkPrinting(L10nLkVatCommon):
    """l10n_lk_print_as_tax_invoice toggle and the report-redirect chokepoints.

    Three independent entry points must all honour the same toggle: the
    in-form Print button (account_move.action_print_pdf), the cog-wheel
    Print menu / any explicit caller of report_action(), and the
    Send & Print wizard / report controller (_pre_render_qweb_pdf). Each
    is tested separately since they are different code paths with no
    shared call chain.
    """

    # ── action_print_pdf (the in-form Print button) ──────────────────────────

    def test_action_print_pdf_uses_gazette_report_when_toggle_on(self):
        invoice = self._make_invoice("out_invoice", post=True)
        action = invoice.with_context(discard_logo_check=True).action_print_pdf()
        self.assertEqual(action["report_name"], "l10n_lk_vat.report_vat_invoice")

    def test_action_print_pdf_uses_gazette_report_when_toggle_off(self):
        # Non-VAT buyers get the same gazette design titled INVOICE (2481/22 alignment).
        invoice = self._make_invoice("out_invoice", post=True)
        invoice.l10n_lk_print_as_tax_invoice = False
        action = invoice.with_context(discard_logo_check=True).action_print_pdf()
        self.assertEqual(action["report_name"], "l10n_lk_vat.report_vat_invoice")

    def test_action_print_pdf_falls_back_when_lk_vat_disabled(self):
        self.env.company.l10n_lk_vat_enabled = False
        invoice = self._make_invoice("out_invoice", post=True)
        action = invoice.with_context(discard_logo_check=True).action_print_pdf()
        self.assertEqual(action["report_name"], "account.report_invoice_with_payments")

    # ── ir.actions.report.report_action() ────────────────────────────────────
    # Defensive backstop for explicit callers - NOT the path the cog-wheel
    # Print menu or the Send & Print wizard actually use (see below), but
    # still real code that must behave correctly for any other caller.

    def test_report_action_redirects_default_invoice_action_when_toggle_on(self):
        invoice = self._make_invoice("out_invoice", post=True)
        default_action = self.env.ref("account.account_invoices")
        action = default_action.report_action(invoice.id, config=False)
        self.assertEqual(action["report_name"], "l10n_lk_vat.report_vat_invoice")

    def test_report_action_redirects_when_toggle_off(self):
        invoice = self._make_invoice("out_invoice", post=True)
        invoice.l10n_lk_print_as_tax_invoice = False
        default_action = self.env.ref("account.account_invoices")
        action = default_action.report_action(invoice.id, config=False)
        self.assertEqual(action["report_name"], "l10n_lk_vat.report_vat_invoice")

    def test_report_action_does_not_redirect_when_lk_vat_disabled(self):
        self.env.company.l10n_lk_vat_enabled = False
        invoice = self._make_invoice("out_invoice", post=True)
        default_action = self.env.ref("account.account_invoices")
        action = default_action.report_action(invoice.id, config=False)
        self.assertEqual(action["report_name"], "account.report_invoice_with_payments")

    def test_report_action_redirect_requires_every_selected_move_to_qualify(self):
        # Mixed batch (one non-LK document) must fall back for the whole
        # selection rather than guess which template the user wanted.
        qualifies = self._make_invoice("out_invoice", post=True)
        does_not_qualify = self._make_invoice("in_invoice", post=True)
        default_action = self.env.ref("account.account_invoices")
        action = default_action.report_action([qualifies.id, does_not_qualify.id], config=False)
        self.assertEqual(action["report_name"], "account.report_invoice_with_payments")

    def test_report_action_unaffected_for_other_actions(self):
        # The redirect only ever applies to account.account_invoices itself -
        # calling report_action() on our own action must behave normally.
        invoice = self._make_invoice("out_invoice", post=True)
        our_action = self.env.ref("l10n_lk_vat.action_report_vat_invoice")
        action = our_action.report_action(invoice.id, config=False)
        self.assertEqual(action["report_name"], "l10n_lk_vat.report_vat_invoice")

    # ── ir.actions.report._pre_render_qweb_pdf() ─────────────────────────────
    # This is the real chokepoint: the cog-wheel Print menu (via the
    # /report/download controller) and account.move.send (Send & Print)
    # both reach here with the report_name STRING, never via report_action().
    #
    # data={"context": {}} mimics what the /report/download controller
    # normally injects - our own template reads context.get(...) for the
    # COPY ONLY guard, which would otherwise KeyError when this method is
    # called directly, bypassing the controller.

    def test_pre_render_qweb_pdf_redirects_default_report_when_toggle_on(self):
        invoice = self._make_invoice("out_invoice", post=True)
        report = self.env["ir.actions.report"]
        content, report_type = report._pre_render_qweb_pdf(
            "account.report_invoice_with_payments", res_ids=[invoice.id], data={"context": {}}
        )
        self.assertEqual(report_type, "html")
        html = content.decode() if isinstance(content, bytes) else content
        self.assertIn("TAX INVOICE", html)

    def test_pre_render_qweb_pdf_gazette_invoice_title_when_toggle_off(self):
        invoice = self._make_invoice("out_invoice", post=True)
        invoice.l10n_lk_print_as_tax_invoice = False
        html = self._render_html(invoice, report="account.report_invoice_with_payments")
        self.assertNotIn("TAX INVOICE", html)
        self.assertIn("<b>INVOICE</b>", html)
        self.assertIn("Date of Supply", html)

    def test_pre_render_qweb_pdf_does_not_redirect_when_lk_vat_disabled(self):
        self.env.company.l10n_lk_vat_enabled = False
        invoice = self._make_invoice("out_invoice", post=True)
        report = self.env["ir.actions.report"]
        content, report_type = report._pre_render_qweb_pdf(
            "account.report_invoice_with_payments", res_ids=[invoice.id], data={"context": {}}
        )
        html = content.decode() if isinstance(content, bytes) else content
        self.assertNotIn("TAX INVOICE", html)

    # ── Helper methods ────────────────────────────────────────────────────────

    def test_is_default_invoice_report_true_for_string_name(self):
        report = self.env["ir.actions.report"]
        self.assertTrue(report._is_default_invoice_report("account.report_invoice_with_payments"))

    def test_is_default_invoice_report_false_for_gazette_string_name(self):
        report = self.env["ir.actions.report"]
        self.assertFalse(report._is_default_invoice_report("l10n_lk_vat.report_vat_invoice"))

    def test_is_default_invoice_report_true_for_action_record(self):
        report = self.env["ir.actions.report"]
        default_action = self.env.ref("account.account_invoices")
        self.assertTrue(report._is_default_invoice_report(default_action))

    def test_is_default_invoice_action_true_for_core_action(self):
        default_action = self.env.ref("account.account_invoices")
        self.assertTrue(default_action._is_default_invoice_action())

    def test_is_default_invoice_action_false_for_gazette_action(self):
        our_action = self.env.ref("l10n_lk_vat.action_report_vat_invoice")
        self.assertFalse(our_action._is_default_invoice_action())
