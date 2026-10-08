from odoo import fields, models


class L10nLkResetOriginalPrint(models.TransientModel):
    _name = "l10n_lk.reset.original.print"
    _description = "Reset Original Print of a Sri Lanka VAT Invoice"

    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice",
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        required=True,
        help="Why the original print is being reset (e.g. printer jam, wrong paper). "
        "Logged permanently on the invoice chatter.",
    )

    def action_reset(self):
        self.ensure_one()
        # Group check + logging are enforced in the model method (RPC-safe).
        self.move_id.l10n_lk_reset_original_print(self.reason)
        return {"type": "ir.actions.act_window_close"}
