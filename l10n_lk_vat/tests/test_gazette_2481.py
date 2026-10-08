from datetime import date

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import L10nLkVatCommon

COPY_MARK = "rotate(-12deg)"  # the COPY ONLY rubber stamp


def _num(move):
    return int(move.name.rsplit("_", 1)[-1])


@tagged("post_install", "-at_install")
class TestL10nLkSequenceReset(L10nLkVatCommon):
    """Change 2: per-journal serial reset policy (continuous / yearly / monthly)."""

    def _journal(self, code, reset):
        return self.env["account.journal"].create(
            {
                "name": f"Sales {code}",
                "code": code[:5],
                "type": "sale",
                "l10n_lk_vat_unit_code": code,
                "l10n_lk_vat_sequence_reset": reset,
                "company_id": self.company_data["company"].id,
            }
        )

    def test_default_reset_is_continuous(self):
        self.assertEqual(self.company_data["default_journal_sale"].l10n_lk_vat_sequence_reset, "continuous")

    def test_continuous_continues_across_month_rollover(self):
        journal = self._journal("CONT1", "continuous")
        jul1 = self._make_invoice(invoice_date=date(2026, 7, 2), post=True, journal=journal)
        jul2 = self._make_invoice(invoice_date=date(2026, 7, 30), post=True, journal=journal)
        refund = self._make_invoice("out_refund", invoice_date=date(2026, 7, 31), post=True, journal=journal)
        aug1 = self._make_invoice(invoice_date=date(2026, 8, 1), post=True, journal=journal)
        jan27 = self._make_invoice(invoice_date=date(2027, 1, 5), post=True, journal=journal)
        self.assertEqual(jul1.name, "26JUL_CONT1_1")
        self.assertEqual(jul2.name, "26JUL_CONT1_2")
        self.assertEqual(refund.name, "26JUL_CONT1_3")  # credit notes share the counter
        self.assertEqual(aug1.name, "26AUG_CONT1_4")  # prefix changes, number continues
        self.assertEqual(jan27.name, "27JAN_CONT1_5")  # also across years

    def test_continuous_backdated_in_same_transaction_never_duplicates(self):
        # Mixin's cache is keyed per YYMMM prefix; a back-dated invoice posted
        # after a later month in the same transaction must not reuse a number.
        journal = self._journal("CONT2", "continuous")
        jul = self._make_invoice(invoice_date=date(2026, 7, 10), post=True, journal=journal)
        aug = self._make_invoice(invoice_date=date(2026, 8, 10), post=True, journal=journal)
        jul_late = self._make_invoice(invoice_date=date(2026, 7, 20), post=True, journal=journal)
        aug2 = self._make_invoice(invoice_date=date(2026, 8, 11), post=True, journal=journal)
        numbers = [_num(m) for m in (jul, aug, jul_late, aug2)]
        self.assertEqual(numbers, [1, 2, 3, 4])
        self.assertEqual(jul_late.name, "26JUL_CONT2_3")

    def test_continuous_debit_note_shares_counter(self):
        journal = self._journal("CONT3", "continuous")
        inv = self._make_invoice(invoice_date=date(2026, 9, 1), post=True, journal=journal)
        debit_wiz = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=inv.ids)
            .create({"reason": "price difference", "date": date(2026, 10, 2), "copy_lines": True})
        )
        debit = self.env["account.move"].browse(debit_wiz.create_debit()["res_id"])
        debit.invoice_date = date(2026, 10, 2)
        debit.action_post()
        self.assertEqual(debit.name, "26OCT_CONT3_2")

    def test_yearly_restarts_in_january(self):
        journal = self._journal("YR1", "yearly")
        nov = self._make_invoice(invoice_date=date(2026, 11, 3), post=True, journal=journal)
        dec = self._make_invoice(invoice_date=date(2026, 12, 3), post=True, journal=journal)
        jan = self._make_invoice(invoice_date=date(2027, 1, 3), post=True, journal=journal)
        feb = self._make_invoice(invoice_date=date(2027, 2, 3), post=True, journal=journal)
        self.assertEqual(
            [nov.name, dec.name, jan.name, feb.name],
            ["26NOV_YR1_1", "26DEC_YR1_2", "27JAN_YR1_1", "27FEB_YR1_2"],
        )

    def test_monthly_restarts_each_month(self):
        journal = self._journal("MON1", "monthly")
        a = self._make_invoice(invoice_date=date(2026, 10, 1), post=True, journal=journal)
        b = self._make_invoice(invoice_date=date(2026, 10, 2), post=True, journal=journal)
        c = self._make_invoice(invoice_date=date(2026, 11, 1), post=True, journal=journal)
        d = self._make_invoice(invoice_date=date(2026, 10, 3), post=True, journal=journal)
        self.assertEqual(
            [a.name, b.name, c.name, d.name],
            ["26OCT_MON1_1", "26OCT_MON1_2", "26NOV_MON1_1", "26OCT_MON1_3"],
        )

    def test_counters_isolated_per_journal_unit(self):
        j1 = self._journal("UA", "continuous")
        j2 = self._journal("UB", "continuous")
        a = self._make_invoice(invoice_date=date(2026, 10, 1), post=True, journal=j1)
        b = self._make_invoice(invoice_date=date(2026, 10, 1), post=True, journal=j2)
        self.assertEqual((a.name, b.name), ("26OCT_UA_1", "26OCT_UB_1"))

    def test_serial_has_no_spaces_and_max_40_chars(self):
        journal = self._journal("BRANCH03COLOMBO", "continuous")
        inv = self._make_invoice(invoice_date=date(2026, 10, 1), post=True, journal=journal)
        self.assertEqual(inv.name, "26OCT_BRANCH03COLOMBO_1")
        self.assertNotIn(" ", inv.name)
        self.assertLessEqual(len(inv.name), 40)


@tagged("post_install", "-at_install")
class TestL10nLkLayout2481(L10nLkVatCommon):
    """Changes 3-6: layout, discount column, foreign currency, non-VAT buyers, gazette 4.2."""

    def test_layout_date_of_supply_and_optional_place(self):
        inv = self._make_invoice(post=True)
        inv.l10n_lk_place_of_supply = False
        html = self._render_html(inv)
        self.assertIn("<b>TAX INVOICE</b>", html)
        self.assertIn("Date of Supply", html)
        self.assertNotIn("Date of Delivery", html)
        self.assertNotIn("Place of Supply:", html)
        self.assertIn("Purchaser's TIN", html)
        inv2 = self._make_invoice(post=True)
        inv2.l10n_lk_place_of_supply = "Kandy"
        self.assertIn("Place of Supply:", self._render_html(inv2))

    def test_amounts_keep_cents(self):
        inv = self._make_invoice(post=True, line_vals={"price_unit": 1234.56, "tax_ids": [Command.clear()]})
        html = self._render_html(inv)
        self.assertIn("1,234.56", html)

    def test_discount_column_only_when_discount(self):
        plain = self._make_invoice(post=True)
        self.assertNotIn("Disc. %", self._render_html(plain))
        disc = self._make_invoice(
            post=True,
            line_vals={"quantity": 3, "price_unit": 200.0, "discount": 10.0, "tax_ids": [Command.clear()]},
        )
        html = self._render_html(disc)
        self.assertIn("Disc. %", html)
        self.assertIn("10.00", html)
        self.assertIn("540.00", html)  # 3 x 200.00 x (1 - 10%)

    def test_discount_unit_price_excl_vat_with_included_tax(self):
        tax = self.env["account.tax"].create(
            {"name": "VAT 18% incl", "amount": 18.0, "price_include_override": "tax_included"}
        )
        inv = self._make_invoice(
            line_vals={"quantity": 2, "price_unit": 118.0, "discount": 50.0, "tax_ids": [Command.set(tax.ids)]}
        )
        line = inv.invoice_line_ids
        self.assertAlmostEqual(line._l10n_lk_vat_unit_price_excl() * 2 * 0.5, line.price_subtotal, places=2)

    def test_foreign_currency_rows_in_lkr(self):
        foreign = self.setup_other_currency("EUR", rates=[("2026-01-01", 0.5)])
        inv = self._make_invoice(
            post=True, currency=foreign, line_vals={"price_unit": 100.0, "tax_ids": [Command.clear()]}
        )
        html = self._render_html(inv)
        self.assertIn("rate used: 1 EUR = 2.0000 LKR", html)
        self.assertIn("Total Value of Supply (LKR)", html)
        self.assertIn("200.00", html)  # 100 EUR at 2 LKR/EUR

    def test_no_foreign_rows_in_company_currency(self):
        inv = self._make_invoice(post=True)
        self.assertNotIn("(LKR):", self._render_html(inv))

    def test_non_vat_customer_prints_invoice_without_purchaser_tin(self):
        inv = self._make_invoice(post=True, partner=self.partner_novat)
        self.assertFalse(inv.l10n_lk_print_as_tax_invoice)
        html = self._render_html(inv)
        self.assertIn("<b>INVOICE</b>", html)
        self.assertNotIn("TAX INVOICE", html)
        self.assertNotIn("Purchaser's TIN", html)
        self.assertIn("Invoice No.:", html)
        self.assertNotIn("Tax Invoice No.:", html)

    def test_non_vat_credit_note_title(self):
        refund = self._make_invoice("out_refund", post=True, partner=self.partner_novat)
        html = self._render_html(refund)
        self.assertIn("<b>CREDIT NOTE</b>", html)
        self.assertNotIn("TAX CREDIT NOTE", html)
        vat_refund = self._make_invoice("out_refund", post=True)
        self.assertIn("<b>TAX CREDIT NOTE</b>", self._render_html(vat_refund))

    def test_non_vat_routed_to_gazette_by_all_paths(self):
        inv = self._make_invoice(post=True, partner=self.partner_novat)
        self.assertEqual(inv.action_print_pdf()["report_name"], "l10n_lk_vat.report_vat_invoice")
        action = self.env.ref("account.account_invoices").report_action(inv.id, config=False)
        self.assertEqual(action["report_name"], "l10n_lk_vat.report_vat_invoice")
        html = self._render_html(inv, report="account.report_invoice_with_payments")
        self.assertIn("<b>INVOICE</b>", html)

    def test_exempt_line_warning_on_tax_invoice(self):
        inv = self._make_invoice(line_vals={"tax_ids": [Command.clear()]})
        self.assertTrue(inv.l10n_lk_print_as_tax_invoice)
        self.assertTrue(inv.l10n_lk_vat_exempt_warning)
        inv.l10n_lk_print_as_tax_invoice = False
        self.assertFalse(inv.l10n_lk_vat_exempt_warning)

    def test_no_warning_with_vat(self):
        tax = self.env["account.tax"].create({"name": "VAT 18%", "amount": 18.0})
        inv = self._make_invoice(line_vals={"tax_ids": [Command.set(tax.ids)]})
        self.assertFalse(inv.l10n_lk_vat_exempt_warning)

    def test_block_exempt_on_tax_invoice_setting(self):
        inv = self._make_invoice(line_vals={"tax_ids": [Command.clear()]})
        inv.action_post()  # default: warning only
        self.assertEqual(inv.state, "posted")
        self.env.company.l10n_lk_vat_block_exempt_on_tax_invoice = True
        inv2 = self._make_invoice(line_vals={"tax_ids": [Command.clear()]})
        with self.assertRaises(UserError):
            inv2.action_post()
        inv2.l10n_lk_print_as_tax_invoice = False
        inv2.action_post()
        self.assertEqual(inv2.state, "posted")


@tagged("post_install", "-at_install")
class TestL10nLkOriginalLock(L10nLkVatCommon):
    """Changes 7 + 8: original printed once, COPY ONLY afterwards, copy set."""

    def test_first_render_is_original_then_copy(self):
        inv = self._make_invoice(post=True)
        html = self._render_html(inv, report="account.report_invoice_with_payments")
        self.assertTrue(inv.l10n_lk_original_printed)
        self.assertEqual(inv.l10n_lk_original_printed_by, self.env.user)
        self.assertTrue(inv.l10n_lk_original_printed_date)
        self.assertNotIn(COPY_MARK, html)
        self.assertEqual(inv.l10n_lk_copy_count, 0)
        self.assertTrue(any("ORIGINAL printed via" in (m.body or "") for m in inv.message_ids))

        html2 = self._render_html(inv)  # e.g. a second Send & Print / Print menu
        self.assertIn(COPY_MARK, html2)
        self.assertEqual(inv.l10n_lk_copy_count, 1)
        self.assertTrue(any("Reprint as COPY ONLY via" in (m.body or "") for m in inv.message_ids))

    def test_draft_render_does_not_mark_original(self):
        inv = self._make_invoice()
        self._render_html(inv)
        self.assertFalse(inv.l10n_lk_original_printed)

    def test_print_button_opens_copy_wizard_after_original(self):
        inv = self._make_invoice(post=True)
        self.assertEqual(inv.action_print_pdf()["type"], "ir.actions.report")
        self._render_html(inv)
        action = inv.action_print_pdf()
        self.assertEqual(action["res_model"], "l10n_lk.copy.invoice")
        self.assertEqual(action["context"]["default_move_id"], inv.id)

    def test_copy_wizard_render_is_logged_once(self):
        inv = self._make_invoice(post=True)
        self._render_html(inv)
        wizard = self.env["l10n_lk.copy.invoice"].create({"move_id": inv.id, "reason": "Customer lost it"})
        action = wizard.action_generate_copy()
        self.assertEqual(inv.l10n_lk_copy_count, 1)
        html = self._render_html(inv, **action["context"])
        self.assertIn(COPY_MARK, html)
        self.assertEqual(inv.l10n_lk_copy_count, 1)  # not double counted
        self.assertFalse(inv.l10n_lk_copy_pending)

    def test_forged_copy_mode_on_unprinted_invoice_renders_original(self):
        inv = self._make_invoice(post=True)
        html = self._render_html(inv, l10n_lk_vat_copy_mode=True)
        self.assertNotIn(COPY_MARK, html)
        self.assertTrue(inv.l10n_lk_original_printed)
        self.assertEqual(inv.l10n_lk_copy_count, 0)

    def test_reset_original_print_manager_only(self):
        inv = self._make_invoice(post=True)
        self._render_html(inv)
        self.env.user.group_ids -= self.env.ref("account.group_account_manager")
        with self.assertRaises(AccessError):
            inv.l10n_lk_reset_original_print("misprint")
        self.env.user.group_ids |= self.env.ref("account.group_account_manager")
        wizard = self.env["l10n_lk.reset.original.print"].create({"move_id": inv.id, "reason": "Printer jam"})
        wizard.action_reset()
        self.assertFalse(inv.l10n_lk_original_printed)
        self.assertTrue(any("Printer jam" in (m.body or "") for m in inv.message_ids))
        html = self._render_html(inv)
        self.assertNotIn(COPY_MARK, html)
        self.assertTrue(inv.l10n_lk_original_printed)

    def test_copy_set_on_original_single_copy_on_reprint(self):
        self.env.company.l10n_lk_vat_copy_set_enabled = True
        labels = self.env.company._l10n_lk_vat_copy_label_list()
        self.assertEqual(len(labels), 4)
        self.assertEqual(labels[3], "Quadruplicate - Customer Copy")
        inv = self._make_invoice(post=True)
        html = self._render_html(inv)
        for label in labels:
            self.assertIn(label, html)
        self.assertEqual(html.count('class="article"'), 4)
        html2 = self._render_html(inv)
        self.assertEqual(html2.count('class="article"'), 1)
        self.assertNotIn("Duplicate - Accounts", html2)
        self.assertIn(COPY_MARK, html2)

    def test_copy_set_disabled_renders_once(self):
        inv = self._make_invoice(post=True)
        html = self._render_html(inv)
        self.assertEqual(html.count('class="article"'), 1)
        self.assertNotIn("Original - Customer", html)
