import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Gazette 2481/22 clause 4.1.a.iii + IRD circular SEC/2026/E/03 section 4.4:
# "Data length for QQQQ is 1 to 15 characters. It is allowed numbers, letters or mixed."
# The full serial number must not contain spaces, so neither may the unit code.
# Underscores are excluded as well because "_" is the gazette field separator.
L10N_LK_UNIT_CODE_MAX = 15
L10N_LK_UNIT_CODE_RE = re.compile(r"^[A-Za-z0-9]{1,%d}$" % L10N_LK_UNIT_CODE_MAX)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_lk_vat_unit_code = fields.Char(
        string="VAT Unit Code (QQQQ)",
        size=L10N_LK_UNIT_CODE_MAX,
        default="MAIN",
        help="Alphanumeric code (1-15 letters/digits, no spaces or underscores) identifying this "
        "branch/unit/section in the gazette invoice serial number format YYMMM_QQQQ_XXXXX "
        '(e.g. "HEAD", "BR03", "SALES").',
    )
    l10n_lk_vat_sequence_reset = fields.Selection(
        selection=[
            ("continuous", "Continuous (never resets)"),
            ("yearly", "Restart every January"),
            ("monthly", "Restart every month"),
        ],
        string="VAT Serial Reset",
        default="continuous",
        required=True,
        help="Controls the numeric XXXXX part of the gazette serial number YYMMM_QQQQ_XXXXX.\n"
        "Continuous (gazette default): the number continues from the last number issued by this "
        "journal/unit, even when the YYMMM prefix changes at the start of a new month.\n"
        "Yearly: the number restarts at 1 every January.\n"
        "Monthly: the number restarts at 1 every month.\n"
        "Invoices, credit notes and debit notes of the journal always share one counter.",
    )

    @api.constrains("l10n_lk_vat_unit_code", "type")
    def _check_l10n_lk_vat_unit_code(self):
        for journal in self:
            code = journal.l10n_lk_vat_unit_code
            if code and not L10N_LK_UNIT_CODE_RE.match(code):
                raise ValidationError(
                    _(
                        'Journal "%(journal)s": the VAT Unit Code (QQQQ) "%(code)s" is invalid. '
                        "It must be 1 to 15 letters and/or digits, without spaces, underscores "
                        "or other symbols (gazette 2481/22, clause 4.1.a.iii).",
                        journal=journal.name,
                        code=code,
                    )
                )
            if journal.company_id.l10n_lk_vat_enabled and journal.type == "sale" and not code:
                raise ValidationError(
                    _(
                        'Journal "%s": A VAT Unit Code (QQQQ) is required for all Sales journals '
                        "when Sri Lanka VAT Compliance is enabled.",
                        journal.name,
                    )
                )
