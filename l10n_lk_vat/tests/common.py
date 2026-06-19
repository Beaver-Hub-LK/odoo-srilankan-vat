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

    def _make_invoice(self, move_type="out_invoice", invoice_date=None, post=False, journal=None):
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
        move = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner_a.id,
                "invoice_date": invoice_date or date(2026, 6, 1),
                "journal_id": journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": account.id,
                        },
                    )
                ],
            }
        )
        if post:
            move.action_post()
        return move
