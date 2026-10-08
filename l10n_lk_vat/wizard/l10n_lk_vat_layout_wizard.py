from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class L10nLkVatLayoutWizard(models.TransientModel):
    """
    Dedicated wizard for configuring the VAT Invoice layout.
    Mirrors the pattern of base.document.layout but focused on the
    Sri Lanka VAT-specific settings stored on res.company.
    Opened via "Configure VAT Invoice Layout" button in Settings.
    """

    _name = "l10n_lk.vat.layout.wizard"
    _description = "Sri Lanka VAT Invoice Layout"

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    # ── Layout settings (related to res.company) ─────────────────────────────
    l10n_lk_vat_layout = fields.Selection(
        related="company_id.l10n_lk_vat_layout",
        readonly=False,
        string="VAT Invoice Layout",
    )
    l10n_lk_vat_show_logo = fields.Boolean(
        related="company_id.l10n_lk_vat_show_logo",
        readonly=False,
        string="Show Logo",
    )
    l10n_lk_vat_signatory_name = fields.Char(
        related="company_id.l10n_lk_vat_signatory_name",
        readonly=False,
        string="Authorized Signatory Name",
    )
    l10n_lk_vat_signatory_designation = fields.Char(
        related="company_id.l10n_lk_vat_signatory_designation",
        readonly=False,
        string="Authorized Signatory Designation",
    )
    l10n_lk_vat_footer_text = fields.Text(
        related="company_id.l10n_lk_vat_footer_text",
        readonly=False,
        string="Invoice Footer",
    )
    l10n_lk_vat_show_signature_box = fields.Boolean(
        related="company_id.l10n_lk_vat_show_signature_box",
        readonly=False,
        string="Show Blank Signature Box",
    )
    l10n_lk_vat_show_amount_in_words = fields.Boolean(
        related="company_id.l10n_lk_vat_show_amount_in_words",
        readonly=False,
        string="Show Total Amount in Words",
    )
    l10n_lk_vat_rate = fields.Float(
        related="company_id.l10n_lk_vat_rate",
        readonly=False,
        string="VAT Rate (%)",
    )

    l10n_lk_vat_copy_set_enabled = fields.Boolean(
        related="company_id.l10n_lk_vat_copy_set_enabled",
        readonly=False,
        string="Print Copy Set on Original",
    )
    l10n_lk_vat_copy_labels = fields.Text(
        related="company_id.l10n_lk_vat_copy_labels",
        readonly=False,
        string="Copy Set Labels",
    )
    l10n_lk_vat_block_exempt_on_tax_invoice = fields.Boolean(
        related="company_id.l10n_lk_vat_block_exempt_on_tax_invoice",
        readonly=False,
        string="Block Exempt Lines on Tax Invoices",
    )

    # ── Constraints ──────────────────────────────────────────────────────────

    @api.constrains("company_id")
    def _check_company_access(self):
        """Prevent configuring a company the current user does not belong to.

        company_id is invisible in the UI but writable via direct RPC.
        Restricting to user.company_ids ensures a multi-company manager
        cannot target a company outside their own set.
        """
        for wizard in self:
            if wizard.company_id not in self.env.user.company_ids:
                raise ValidationError(
                    _(
                        'You do not have access to configure VAT Invoice Layout for company "%s".',
                        wizard.company_id.name,
                    )
                )

    def action_save(self):
        """Close the wizard - no explicit write() is needed.

        All fields are declared with ``related='company_id.<field>'`` and
        ``readonly=False``.  Odoo's form view writes through related fields
        automatically when the wizard record is saved (before this method is
        called), so the data is already on ``res.company`` by the time we
        return the close action.
        """
        return {"type": "ir.actions.act_window_close"}
