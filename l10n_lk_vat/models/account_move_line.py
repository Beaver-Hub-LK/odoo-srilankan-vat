from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _l10n_lk_vat_unit_price_excl(self):
        """Unit price excluding VAT, so Qty x Unit Price x (1 - Disc. %) = Amount excl. VAT.

        For price-excluded taxes this is simply price_unit. With tax-included
        prices the printed unit price is derived back from the line's
        untaxed subtotal, keeping the printed arithmetic consistent.
        """
        self.ensure_one()
        taxes = self.tax_ids.flatten_taxes_hierarchy()
        if any(tax.price_include for tax in taxes):
            factor = self.quantity * (1.0 - (self.discount or 0.0) / 100.0)
            if factor:
                return self.price_subtotal / factor
        return self.price_unit
