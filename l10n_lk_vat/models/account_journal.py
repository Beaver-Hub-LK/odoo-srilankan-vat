from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_lk_vat_unit_code = fields.Char(
        string="VAT Unit Code (QQQQ)",
        size=4,
        default="MAIN",
        help="Alphanumeric code identifying this branch/unit/section in the gazette invoice "
        'serial number format YYMMM_QQQQ_XXXXX (e.g. "HEAD", "BR03", "SALES").',
    )

    @api.constrains("l10n_lk_vat_unit_code", "type")
    def _check_l10n_lk_vat_unit_code(self):
        for journal in self:
            if journal.company_id.l10n_lk_vat_enabled and journal.type == "sale" and not journal.l10n_lk_vat_unit_code:
                raise ValidationError(
                    _(
                        'Journal "%s": A VAT Unit Code (QQQQ) is required for all Sales journals '
                        "when Sri Lanka VAT Compliance is enabled.",
                        journal.name,
                    )
                )
