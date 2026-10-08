from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import L10nLkVatCommon


@tagged("post_install", "-at_install")
class TestL10nLkFields(L10nLkVatCommon):
    """Field defaults, computed fields, and constraint checks."""

    # ── l10n_lk_place_of_supply ──────────────────────────────────────────────

    def test_place_of_supply_defaults_to_company_city(self):
        self.env.company.city = "Kandy"
        invoice = self._make_invoice("out_invoice")
        self.assertEqual(invoice.l10n_lk_place_of_supply, "Kandy")

    def test_place_of_supply_empty_string_when_no_city(self):
        self.env.company.city = False
        invoice = self._make_invoice("out_invoice")
        self.assertEqual(invoice.l10n_lk_place_of_supply, "")

    def test_place_of_supply_is_user_editable(self):
        invoice = self._make_invoice("out_invoice")
        invoice.l10n_lk_place_of_supply = "Galle"
        self.assertEqual(invoice.l10n_lk_place_of_supply, "Galle")

    # ── show_taxable_supply_date override ────────────────────────────────────

    def test_show_taxable_supply_date_true_for_lk_invoice(self):
        invoice = self._make_invoice("out_invoice")
        self.assertTrue(invoice.show_taxable_supply_date)

    def test_show_taxable_supply_date_true_for_lk_credit_note(self):
        refund = self._make_invoice("out_refund")
        self.assertTrue(refund.show_taxable_supply_date)

    def test_show_taxable_supply_date_false_when_lk_disabled(self):
        self.env.company.l10n_lk_vat_enabled = False
        invoice = self._make_invoice("out_invoice")
        # Base Odoo does not set this True for regular invoices without LK VAT
        self.assertFalse(invoice.show_taxable_supply_date)

    # ── l10n_lk_mode_of_payment ──────────────────────────────────────────────

    def test_mode_of_payment_writable_on_draft(self):
        invoice = self._make_invoice("out_invoice")
        invoice.l10n_lk_mode_of_payment = "bank_transfer"
        self.assertEqual(invoice.l10n_lk_mode_of_payment, "bank_transfer")

    def test_mode_of_payment_selection_values(self):
        invoice = self._make_invoice("out_invoice")
        allowed = {v[0] for v in invoice._fields["l10n_lk_mode_of_payment"].selection}
        expected = {"cash", "bank_transfer", "cheque", "credit_card", "debit_card", "mobile_payment", "online_payment"}
        self.assertEqual(allowed, expected)

    # ── l10n_lk_print_as_tax_invoice ──────────────────────────────────────────

    def test_print_as_tax_invoice_defaults_to_true_for_vat_customer(self):
        invoice = self._make_invoice("out_invoice")
        self.assertTrue(invoice.l10n_lk_print_as_tax_invoice)

    def test_print_as_tax_invoice_defaults_to_false_for_non_vat_customer(self):
        invoice = self._make_invoice("out_invoice", partner=self.partner_novat)
        self.assertFalse(invoice.l10n_lk_print_as_tax_invoice)

    def test_print_as_tax_invoice_follows_partner_in_draft_frozen_when_posted(self):
        invoice = self._make_invoice("out_invoice", partner=self.partner_novat)
        invoice.partner_id = self.partner_a
        self.assertTrue(invoice.l10n_lk_print_as_tax_invoice)
        invoice.action_post()
        self.partner_a.vat = False
        invoice.invalidate_recordset()
        self.assertTrue(invoice.l10n_lk_print_as_tax_invoice)

    def test_print_as_tax_invoice_is_user_editable(self):
        invoice = self._make_invoice("out_invoice")
        invoice.l10n_lk_print_as_tax_invoice = False
        self.assertFalse(invoice.l10n_lk_print_as_tax_invoice)

    # ── res.company fields ───────────────────────────────────────────────────

    def test_vat_rate_default_is_18(self):
        # setUpClass enables LK VAT but does not change the rate; default is 18.0
        self.assertEqual(self.env.company.l10n_lk_vat_rate, 18.0)

    def test_vat_rate_is_configurable(self):
        self.env.company.l10n_lk_vat_rate = 15.0
        self.assertEqual(self.env.company.l10n_lk_vat_rate, 15.0)

    def test_show_amount_in_words_defaults_to_true(self):
        self.assertTrue(self.env.company.l10n_lk_vat_show_amount_in_words)

    # ── Journal unit-code constraint ─────────────────────────────────────────

    def test_sale_journal_requires_unit_code_when_lk_enabled(self):
        with self.assertRaises(ValidationError):
            self.env["account.journal"].create(
                {
                    "name": "Test Sales Journal",
                    "type": "sale",
                    "code": "TSLS",
                    "l10n_lk_vat_unit_code": False,  # default is MAIN - clear it explicitly
                }
            )

    def test_purchase_journal_does_not_require_unit_code(self):
        journal = self.env["account.journal"].create(
            {
                "name": "Test Purchase Journal",
                "type": "purchase",
                "code": "TPRC",
                "l10n_lk_vat_unit_code": False,
            }
        )
        self.assertFalse(journal.l10n_lk_vat_unit_code)

    def test_sale_journal_no_unit_code_required_when_lk_disabled(self):
        self.env.company.l10n_lk_vat_enabled = False
        journal = self.env["account.journal"].create(
            {
                "name": "Test Sales Journal Disabled",
                "type": "sale",
                "code": "TSLS2",
                "l10n_lk_vat_unit_code": False,
            }
        )
        self.assertFalse(journal.l10n_lk_vat_unit_code)

    def test_unit_code_max_15_chars(self):
        # Gazette 2481/22 4.1.a.iii / IRD circular 4.4: QQQQ is 1 to 15 characters.
        field = self.env["account.journal"]._fields["l10n_lk_vat_unit_code"]
        self.assertEqual(field.size, 15)

    def test_unit_code_default_main(self):
        journal = self.env["account.journal"].create({"name": "Default Code", "type": "sale", "code": "DFC1"})
        self.assertEqual(journal.l10n_lk_vat_unit_code, "MAIN")

    def test_unit_code_15_alnum_is_valid(self):
        journal = self.env["account.journal"].create(
            {"name": "Long Code", "type": "sale", "code": "LNG1", "l10n_lk_vat_unit_code": "BRANCH03COLOMBO"}
        )
        self.assertEqual(journal.l10n_lk_vat_unit_code, "BRANCH03COLOMBO")

    def test_unit_code_rejects_space_underscore_symbols(self):
        journal = self.company_data["default_journal_sale"]
        for bad in ("BR 03", "BR_03", "BR-03", "BR/3"):
            with self.subTest(code=bad), self.assertRaises(ValidationError):
                journal.l10n_lk_vat_unit_code = bad

    # ── Layout wizard write-through ──────────────────────────────────────────

    def test_layout_wizard_vat_rate_writes_through_to_company(self):
        self.env["l10n_lk.vat.layout.wizard"].create(
            {
                "company_id": self.env.company.id,
                "l10n_lk_vat_rate": 15.5,
            }
        )
        self.assertEqual(self.env.company.l10n_lk_vat_rate, 15.5)

    def test_layout_wizard_signatory_writes_through_to_company(self):
        self.env["l10n_lk.vat.layout.wizard"].create(
            {
                "company_id": self.env.company.id,
                "l10n_lk_vat_signatory_name": "Kamal Perera",
                "l10n_lk_vat_signatory_designation": "Finance Manager",
            }
        )
        self.assertEqual(self.env.company.l10n_lk_vat_signatory_name, "Kamal Perera")
        self.assertEqual(self.env.company.l10n_lk_vat_signatory_designation, "Finance Manager")

    def test_layout_wizard_show_amount_in_words_writes_through_to_company(self):
        self.env["l10n_lk.vat.layout.wizard"].create(
            {
                "company_id": self.env.company.id,
                "l10n_lk_vat_show_amount_in_words": False,
            }
        )
        self.assertFalse(self.env.company.l10n_lk_vat_show_amount_in_words)

    def test_layout_wizard_action_save_returns_close(self):
        wizard = self.env["l10n_lk.vat.layout.wizard"].create(
            {
                "company_id": self.env.company.id,
            }
        )
        action = wizard.action_save()
        self.assertEqual(action["type"], "ir.actions.act_window_close")

    # ── VAT rate range constraint (security fix) ─────────────────────────────

    def test_vat_rate_negative_raises(self):
        with self.assertRaises(ValidationError):
            self.env.company.l10n_lk_vat_rate = -1.0

    def test_vat_rate_over_100_raises(self):
        with self.assertRaises(ValidationError):
            self.env.company.l10n_lk_vat_rate = 101.0

    def test_vat_rate_zero_is_valid(self):
        self.env.company.l10n_lk_vat_rate = 0.0
        self.assertEqual(self.env.company.l10n_lk_vat_rate, 0.0)

    def test_vat_rate_100_is_valid(self):
        self.env.company.l10n_lk_vat_rate = 100.0
        self.assertEqual(self.env.company.l10n_lk_vat_rate, 100.0)

    # ── Company toggle revalidates journals (security fix) ───────────────────

    def test_enable_lk_vat_blocks_when_sales_journal_missing_unit_code(self):
        # Disable first so we can create a journal without the constraint firing
        self.env.company.l10n_lk_vat_enabled = False
        self.env["account.journal"].create(
            {
                "name": "No-Code Sales Journal",
                "type": "sale",
                "code": "NCS1",
                "l10n_lk_vat_unit_code": False,
            }
        )
        with self.assertRaises(ValidationError):
            self.env.company.l10n_lk_vat_enabled = True

    def test_enable_lk_vat_passes_when_all_sales_journals_have_unit_code(self):
        self.env.company.l10n_lk_vat_enabled = False
        self.env["account.journal"].create(
            {
                "name": "Coded Sales Journal",
                "type": "sale",
                "code": "CSJ1",
                "l10n_lk_vat_unit_code": "BR99",
            }
        )
        # Should not raise - all sales journals (including the new one) have codes
        self.env.company.l10n_lk_vat_enabled = True
        self.assertTrue(self.env.company.l10n_lk_vat_enabled)
