{
    "name": "Sri Lanka VAT Invoice Compliance",
    "countries": ["lk"],  # for discoverability; auto_install is False
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Gazette-compliant Tax Invoice, Credit Note & Debit Note for Sri Lanka VAT (effective 2026-01-01)",
    "author": "Beaver Hub (Pvt) Ltd",
    "website": "https://www.beaver-hub.com",
    "depends": [
        "account",
        "account_debit_note",
        "l10n_lk",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/vat_layout_wizard_views.xml",
        "wizard/l10n_lk_copy_invoice_views.xml",
        "views/res_config_settings_views.xml",
        "views/account_journal_views.xml",
        "views/account_move_views.xml",
        "report/report_actions.xml",
        "report/report_vat_invoice.xml",
    ],
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
    "license": "LGPL-3",
}
