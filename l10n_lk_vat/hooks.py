def post_init_hook(env):
    """Backfill l10n_lk_print_as_tax_invoice on pre-existing invoices.

    Odoo always creates new boolean columns with SQL ``DEFAULT false``,
    ignoring the field's Python ``default=True``, and only recomputes
    existing rows for fields that declare ``compute=``. Without this,
    every invoice that existed before this field was added would silently
    fall back to Odoo's default invoice template instead of the gazette
    Tax Invoice. Runs on fresh installs into a database that already has
    invoices. Databases upgrading an already-installed copy of this module
    are not covered - backfill those manually if needed.
    """
    env.cr.execute(
        "UPDATE account_move SET l10n_lk_print_as_tax_invoice = true " "WHERE l10n_lk_print_as_tax_invoice = false"
    )
