from odoo import _, fields, models
from odoo.exceptions import UserError


class L10nLkCopyInvoice(models.TransientModel):
    _name = "l10n_lk.copy.invoice"
    _description = "Print COPY ONLY Reprint of Tax Invoice"

    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice",
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string="Reason for Copy",
        required=True,
        help="Reason the original was lost or why a copy is needed. This is logged permanently on the invoice chatter.",
    )

    def action_generate_copy(self):
        self.ensure_one()
        move = self.move_id

        # Server-side guard - the "Print Copy" button is hidden via invisible= in
        # the view, but invisible= is client-side only.  These checks prevent abuse
        # via direct RPC calls.
        if not move._is_l10n_lk_vat_sequence():
            raise UserError(_("COPY ONLY reprints are only available for Sri Lanka VAT invoices."))
        if move.state != "posted":
            raise UserError(_("A COPY ONLY reprint can only be issued for a confirmed (posted) invoice."))

        move.l10n_lk_increment_copy_count(self.reason)

        return (
            self.env.ref("l10n_lk_vat.action_report_vat_invoice")
            .with_context(
                l10n_lk_vat_copy_mode=True,
            )
            .report_action(move, config=False)
        )
