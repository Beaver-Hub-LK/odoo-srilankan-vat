# Changelog - l10n_lk_vat

All notable changes to this module. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [19.0.2.0.0] - 2026-10-08 - Gazette 2481/22 alignment

Aligns the module with Gazette Extraordinary No. 2481/22 (27 March 2026, Annexure I),
IRD circular SEC/2026/E/03 and Gazette 2500/106 (effective date 1 October 2026).
Version 1.0 targeted the rescinded gazette 2463/05.

### Added
- `account.journal.l10n_lk_vat_sequence_reset`: Continuous (default) / Yearly / Monthly
  serial reset policy, shown on the journal form next to the unit code (4.1.a.iv).
- Discount column ("Disc. %") printed only when a line has a discount; unit price printed
  excluding VAT so the line arithmetic is visibly consistent.
- Foreign-currency documents: Value of Supply, VAT and Total also stated in LKR with the
  rate used (circular 4.7).
- Gazette 4.2 / circular 4.8: computed warning `l10n_lk_vat_exempt_warning` shown as a
  yellow banner on Tax Invoices with no-VAT / 0% / exempt lines, and company setting
  `l10n_lk_vat_block_exempt_on_tax_invoice` (default off) that blocks posting them.
- Original-print lock: `l10n_lk_original_printed`, `l10n_lk_original_printed_date`,
  `l10n_lk_original_printed_by` (tracked). First PDF render of a posted document by any
  path is the ORIGINAL; later renders are automatically COPY ONLY, counted and logged.
  The Print button on a printed document opens the Print Copy wizard.
- "Reset Original Print" wizard (`l10n_lk.reset.original.print`) for accounting managers,
  reason required and logged.
- Copy set: `l10n_lk_vat_copy_set_enabled` / `l10n_lk_vat_copy_labels` on the company
  (VAT Layout wizard, Copies tab); the original renders once per label in one PDF.
- New tests: `tests/test_gazette_2481.py`.

### Changed
- QQQQ unit code: 1-15 letters/digits, no spaces/underscores/symbols (4.1.a.iii); default `MAIN`.
- Serial counter shared by invoices, credit notes and debit notes of the same journal/unit
  (the per-type isolation domain was removed). Month abbreviation no longer depends on the
  server locale.
- `l10n_lk_print_as_tax_invoice` is now computed from the customer's TIN (stored, editable,
  follows the partner in draft, frozen once posted). When off, the same gazette design
  prints as INVOICE / CREDIT NOTE / DEBIT NOTE without purchaser TIN, instead of Odoo's
  default layout - on every print path.
- "Date of Delivery" renamed "Date of Supply"; Place of Supply printed only when set;
  title in bold; totals label "Total Amount/consideration including VAT"; amounts keep
  cents (2 decimals).
- COPY ONLY decision moved server-side (per-transaction state instead of request context).
- Report template renders one `article` per copy (own footer / page numbering) and multi-record
  PDFs are rendered per record so Send & Print can split them.
- `post_init_hook` now initialises `l10n_lk_print_as_tax_invoice` from the customer's TIN.

## [19.0.1.0.0] - 2026-06-19
- Initial release.
