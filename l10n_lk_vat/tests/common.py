from datetime import date

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class L10nLkVatCommon(AccountTestInvoicingCommon):
    """Shared setup for all l10n_lk_vat tests.

    Enables Sri Lanka VAT compliance on the test company and configures
    the default sales journal with a unit code so the gazette constraint
    is satisfied before any test method runs.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Write unit code BEFORE enabling l10n_lk_vat_enabled: the journal
        # constraint (_check_l10n_lk_vat_unit_code) fires on write and checks
        # company.l10n_lk_vat_enabled, so setting the code first avoids a
        # circular constraint failure.
        cls.company_data["default_journal_sale"].write(
            {
                "l10n_lk_vat_unit_code": "HEAD",
            }
        )
        cls.env.company.write(
            {
                "l10n_lk_vat_enabled": True,
                "city": "Colombo",
            }
        )
        # VAT-registered customer (TIN) → documents default to TAX INVOICE.
        cls.partner_a.vat = "123456789"
        # Customer without TIN → documents default to plain INVOICE.
        cls.partner_novat = cls.env["res.partner"].create({"name": "Walk-in Customer"})

    def _make_invoice(
        self,
        move_type="out_invoice",
        invoice_date=None,
        post=False,
        journal=None,
        partner=None,
        line_vals=None,
        currency=None,
    ):
        """Create a minimal invoice/bill suitable for LK VAT testing."""
        if journal is None:
            journal = (
                self.company_data["default_journal_purchase"]
                if move_type in ("in_invoice", "in_refund")
                else self.company_data["default_journal_sale"]
            )
        account = (
            self.company_data["default_account_expense"]
            if move_type in ("in_invoice", "in_refund")
            else self.company_data["default_account_revenue"]
        )
        vals = {
            "name": "Test line",
            "quantity": 1.0,
            "price_unit": 100.0,
            "account_id": account.id,
        }
        vals.update(line_vals or {})
        move = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": (partner or self.partner_a).id,
                **({"currency_id": currency.id} if currency else {}),
                "invoice_date": invoice_date or date(2026, 6, 1),
                "journal_id": journal.id,
                "invoice_line_ids": [(0, 0, vals)],
            }
        )
        if post:
            move.action_post()
        return move

    def _render_html(self, move, report="l10n_lk_vat.report_vat_invoice", **ctx):
        """Render through the PDF chokepoint (returns HTML in test mode)."""
        content, _report_type = (
            self.env["ir.actions.report"]
            .with_context(**ctx)
            ._pre_render_qweb_pdf(report, res_ids=move.ids, data={"context": {}})
        )
        return content.decode() if isinstance(content, bytes) else content
