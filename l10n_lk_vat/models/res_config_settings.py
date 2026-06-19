from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_lk_vat_enabled = fields.Boolean(
        related="company_id.l10n_lk_vat_enabled",
        readonly=False,
        string="Enable Sri Lanka VAT Compliance",
    )
