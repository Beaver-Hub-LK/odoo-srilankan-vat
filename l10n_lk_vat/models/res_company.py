from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    # ── Kill switch ──────────────────────────────────────────────────────────
    l10n_lk_vat_enabled = fields.Boolean(
        string="Enable Sri Lanka VAT Compliance",
        help="Activates gazette-compliant Tax Invoice format, custom invoice serial numbers, "
        "and the VAT Layout Designer for this company.",
    )

    # ── Layout designer settings ─────────────────────────────────────────────
    l10n_lk_vat_layout = fields.Selection(
        selection=[("gazette_default", "Gazette Default")],
        string="VAT Invoice Layout",
        default="gazette_default",
        help="The layout template used when printing VAT-compliant invoices.",
    )
    l10n_lk_vat_show_logo = fields.Boolean(
        string="Show Logo on VAT Invoice",
        default=False,
        help="Optionally display the company logo on the VAT invoice. The gazette format does not require a logo.",
    )
    l10n_lk_vat_signatory_name = fields.Char(
        string="Authorized Signatory Name",
        help="Name of the person authorized to sign VAT invoices. "
        "Printed in the signature area at the bottom of the document.",
    )
    l10n_lk_vat_signatory_designation = fields.Char(
        string="Authorized Signatory Designation",
        help='Job title of the authorized signatory (e.g. "Finance Manager").',
    )
    l10n_lk_vat_footer_text = fields.Text(
        string="VAT Invoice Footer",
        help="Footer text printed at the bottom of all VAT invoices (e.g. bank details, terms & conditions).",
    )
    l10n_lk_vat_show_signature_box = fields.Boolean(
        string="Show Blank Signature Box",
        default=True,
        help="Print a blank box at the bottom of the invoice for a wet signature.",
    )
    l10n_lk_vat_rate = fields.Float(
        string="VAT Rate (%)",
        default=18.0,
        digits=(5, 2),
        help="Current VAT rate as published in the gazette. Printed on the invoice "
        'in the "VAT Amount (Total Value of Supply @ X%)" label.',
    )

    # ── Constraints ──────────────────────────────────────────────────────────

    @api.constrains("l10n_lk_vat_rate")
    def _check_l10n_lk_vat_rate(self):
        for company in self:
            if not (0 <= company.l10n_lk_vat_rate <= 100):
                raise ValidationError(_("VAT Rate must be between 0 and 100 percent."))

    @api.constrains("l10n_lk_vat_enabled")
    def _check_journals_have_unit_code(self):
        """Block enabling VAT compliance when Sales journals are missing a unit code.

        The per-journal constraint fires when a journal is saved, but does not
        retroactively validate existing journals. This company-level constraint
        catches that gap when the kill switch is toggled on.
        """
        for company in self:
            if not company.l10n_lk_vat_enabled:
                continue
            missing = self.env["account.journal"].search(
                [
                    ("company_id", "=", company.id),
                    ("type", "=", "sale"),
                    ("l10n_lk_vat_unit_code", "=", False),
                ]
            )
            if missing:
                names = ", ".join(f'"{j.name}"' for j in missing)
                raise ValidationError(
                    _(
                        "Cannot enable Sri Lanka VAT Compliance: the following Sales "
                        "journals have no VAT Unit Code (QQQQ): %s\n\n"
                        "Set the VAT Unit Code on each Sales journal first.",
                        names,
                    )
                )
