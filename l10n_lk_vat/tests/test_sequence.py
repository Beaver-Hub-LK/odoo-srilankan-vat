from datetime import date

from odoo.tests import tagged

from .common import L10nLkVatCommon


@tagged("post_install", "-at_install")
class TestL10nLkSequence(L10nLkVatCommon):
    """Gazette YYMMM_QQQQ_XXXXX sequence generation and isolation."""

    # ── _is_l10n_lk_vat_sequence ─────────────────────────────────────────────

    def test_is_lk_sequence_out_invoice(self):
        invoice = self._make_invoice("out_invoice")
        self.assertTrue(invoice._is_l10n_lk_vat_sequence())

    def test_is_lk_sequence_out_refund(self):
        refund = self._make_invoice("out_refund")
        self.assertTrue(refund._is_l10n_lk_vat_sequence())

    def test_is_lk_sequence_false_vendor_bill(self):
        bill = self._make_invoice("in_invoice")
        self.assertFalse(bill._is_l10n_lk_vat_sequence())

    def test_is_lk_sequence_false_when_vat_disabled(self):
        self.env.company.l10n_lk_vat_enabled = False
        invoice = self._make_invoice("out_invoice")
        self.assertFalse(invoice._is_l10n_lk_vat_sequence())

    # ── _l10n_lk_vat_get_prefix ──────────────────────────────────────────────

    def test_prefix_january(self):
        invoice = self._make_invoice("out_invoice", invoice_date=date(2026, 1, 15))
        self.assertEqual(invoice._l10n_lk_vat_get_prefix(), "26JAN_HEAD_")

    def test_prefix_june(self):
        invoice = self._make_invoice("out_invoice", invoice_date=date(2026, 6, 10))
        self.assertEqual(invoice._l10n_lk_vat_get_prefix(), "26JUN_HEAD_")

    def test_prefix_uses_journal_unit_code(self):
        # Copy the sales journal and give it a different unit code
        branch_journal = self.company_data["default_journal_sale"].copy(
            {
                "name": "Branch Sales",
                "code": "BSLS",
                "l10n_lk_vat_unit_code": "BR01",
            }
        )
        invoice = self._make_invoice("out_invoice", invoice_date=date(2026, 6, 1), journal=branch_journal)
        self.assertEqual(invoice._l10n_lk_vat_get_prefix(), "26JUN_BR01_")

    # ── _get_starting_sequence ───────────────────────────────────────────────

    def test_starting_sequence_format(self):
        invoice = self._make_invoice("out_invoice", invoice_date=date(2026, 1, 15))
        self.assertEqual(invoice._get_starting_sequence(), "26JAN_HEAD_0")

    def test_starting_sequence_non_lk_delegates_to_super(self):
        # Vendor bills use Odoo's standard starting sequence, not the gazette one
        bill = self._make_invoice("in_invoice", invoice_date=date(2026, 6, 1))
        seq = bill._get_starting_sequence()
        self.assertFalse(seq.startswith("26JUN_"))

    # ── _sequence_matches_date ───────────────────────────────────────────────

    def test_sequence_matches_date_unset_slash(self):
        # Draft invoice with no name yet always matches (Odoo 19 stores False, not '/')
        invoice = self._make_invoice("out_invoice", invoice_date=date(2026, 6, 1))
        self.assertIn(invoice.name, (False, "/"))
        self.assertTrue(invoice._sequence_matches_date())

    def test_sequence_matches_date_correct_prefix(self):
        invoice = self._make_invoice("out_invoice", invoice_date=date(2026, 1, 15))
        invoice.write({"name": "26JAN_HEAD_00001"})
        self.assertTrue(invoice._sequence_matches_date())

    def test_sequence_matches_date_wrong_month(self):
        # February invoice carries a January name → mismatch triggers reassignment
        invoice = self._make_invoice("out_invoice", invoice_date=date(2026, 2, 15))
        invoice.write({"name": "26JAN_HEAD_00001"})
        self.assertFalse(invoice._sequence_matches_date())

    def test_sequence_matches_date_non_lk_delegates_to_super(self):
        # Vendor bills use the standard mixin logic
        bill = self._make_invoice("in_invoice", invoice_date=date(2026, 6, 1))
        # Just verify it does not raise; correctness is the mixin's responsibility
        bill._sequence_matches_date()

    # ── Gazette prefix assigned on post ──────────────────────────────────────

    def test_gazette_prefix_on_post(self):
        invoice = self._make_invoice("out_invoice", invoice_date=date(2026, 6, 1), post=True)
        self.assertTrue(invoice.name.startswith("26JUN_HEAD_"), invoice.name)

    def test_credit_note_gets_gazette_prefix(self):
        refund = self._make_invoice("out_refund", invoice_date=date(2026, 6, 1), post=True)
        self.assertTrue(refund.name.startswith("26JUN_HEAD_"), refund.name)

    def test_unit_code_with_month_like_digits(self):
        """BR03 (the gazette example) must not be parsed as month 03."""
        branch = self.env["account.journal"].create(
            {
                "name": "Branch 03 Sales",
                "code": "BR03",
                "type": "sale",
                "l10n_lk_vat_unit_code": "BR03",
                "company_id": self.company_data["company"].id,
            }
        )
        inv1 = self._make_invoice("out_invoice", invoice_date=date(2026, 8, 4), post=True, journal=branch)
        inv2 = self._make_invoice("out_invoice", invoice_date=date(2026, 8, 5), post=True, journal=branch)
        inv3 = self._make_invoice("out_invoice", invoice_date=date(2026, 9, 1), post=True, journal=branch)
        self.assertEqual(inv1.name, "26AUG_BR03_1")
        self.assertEqual(inv2.name, "26AUG_BR03_2")
        # Continuous (default) policy: the number carries on into the new month.
        self.assertEqual(inv3.name, "26SEP_BR03_3")

    # ── Shared counter across document types ──────────────────────────────────

    def test_invoice_and_credit_note_get_unique_sequential_numbers(self):
        # All document types share one monotonically-increasing counter per
        # journal+month because the (name, journal_id) unique index prevents
        # any two posted documents from carrying the same serial.
        inv1 = self._make_invoice("out_invoice", invoice_date=date(2026, 6, 1), post=True)
        ref1 = self._make_invoice("out_refund", invoice_date=date(2026, 6, 1), post=True)
        inv2 = self._make_invoice("out_invoice", invoice_date=date(2026, 6, 1), post=True)

        for move in (inv1, ref1, inv2):
            self.assertTrue(move.name.startswith("26JUN_HEAD_"), move.name)

        inv1_num = int(inv1.name.rsplit("_", 1)[-1])
        ref1_num = int(ref1.name.rsplit("_", 1)[-1])
        inv2_num = int(inv2.name.rsplit("_", 1)[-1])

        # Numbers are unique and increase in posting order
        self.assertLess(inv1_num, ref1_num)
        self.assertLess(ref1_num, inv2_num)

    # ── Monthly counter isolation ─────────────────────────────────────────────

    def test_monthly_counter_resets(self):
        self.company_data["default_journal_sale"].l10n_lk_vat_sequence_reset = "monthly"
        inv_jan = self._make_invoice("out_invoice", invoice_date=date(2026, 1, 15), post=True)
        inv_feb = self._make_invoice("out_invoice", invoice_date=date(2026, 2, 15), post=True)

        self.assertTrue(inv_jan.name.startswith("26JAN_HEAD_"), inv_jan.name)
        self.assertTrue(inv_feb.name.startswith("26FEB_HEAD_"), inv_feb.name)

        jan_num = int(inv_jan.name.rsplit("_", 1)[-1])
        feb_num = int(inv_feb.name.rsplit("_", 1)[-1])
        # Each month starts its own counter from 1
        self.assertEqual(jan_num, 1)
        self.assertEqual(feb_num, 1)

    def test_consecutive_invoices_same_month_increment(self):
        inv1 = self._make_invoice("out_invoice", invoice_date=date(2026, 6, 1), post=True)
        inv2 = self._make_invoice("out_invoice", invoice_date=date(2026, 6, 15), post=True)
        inv3 = self._make_invoice("out_invoice", invoice_date=date(2026, 6, 30), post=True)

        num1 = int(inv1.name.rsplit("_", 1)[-1])
        num2 = int(inv2.name.rsplit("_", 1)[-1])
        num3 = int(inv3.name.rsplit("_", 1)[-1])

        self.assertEqual(num2, num1 + 1)
        self.assertEqual(num3, num2 + 1)

    # ── Unit code fallback ────────────────────────────────────────────────────

    def test_prefix_falls_back_to_head_when_unit_code_blank(self):
        # The journal constraint blocks blank unit codes while LK VAT is enabled,
        # so disable it first to simulate a journal that bypassed the constraint.
        self.env.company.l10n_lk_vat_enabled = False
        self.company_data["default_journal_sale"].write({"l10n_lk_vat_unit_code": ""})
        invoice = self._make_invoice("out_invoice", invoice_date=date(2026, 6, 1))
        self.assertEqual(invoice._l10n_lk_vat_get_prefix(), "26JUN_HEAD_")
