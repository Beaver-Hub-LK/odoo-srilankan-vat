def post_init_hook(env):
    """Initialise l10n_lk_print_as_tax_invoice on pre-existing customer documents.

    The field is computed from the customer (Tax Invoice only when the
    commercial partner has a Tax ID / TIN), but the compute deliberately
    freezes posted documents, so on a fresh install into a database that
    already has invoices we derive the value once here, with the same rule.
    Databases upgrading an already-installed copy of this module keep their
    existing per-invoice values (nothing is overwritten on upgrade).
    """
    env.cr.execute(
        """
        UPDATE account_move m
           SET l10n_lk_print_as_tax_invoice = COALESCE(p.vat, '') != ''
          FROM res_partner p
         WHERE p.id = m.commercial_partner_id
           AND m.move_type IN ('out_invoice', 'out_refund')
        """
    )
