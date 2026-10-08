# Sri Lanka VAT Invoice Compliance (`l10n_lk_vat`)

Odoo 19 module implementing the gazette-compliant **Tax Invoice**, **Tax Credit Note**, and **Tax Debit Note** format mandated by the Commissioner General of Inland Revenue, Sri Lanka, effective **1 October 2026** (Gazette 2481/22, effective date moved by Gazette 2500/106).

> **Version 19.0.2.0.0** aligns the module with Gazette Extraordinary **No. 2481/22** (27 March 2026) and IRD circular **SEC/2026/E/03**. The earlier gazette 2463/05, for which version 1.0 was written, is rescinded. See [What's new in 2.0](#0-whats-new-in-190200).

> **Legal basis:** *Value Added Tax Act, No. 14 of 2002* - Gazette Extraordinary No. 2481/22, Friday, March 27, 2026, Annexure I - *Tax Invoice Specification*.
> **Clarification:** IRD Circular SEC/2026/E/03 (20 May 2026). **Effective date:** 1 October 2026 per Gazette 2500/106.
> **Official source:** [IRD Gazette Publications](https://www.ird.gov.lk/en/publications/sitepages/Gazette.aspx)

---

## 0. What's new in 19.0.2.0.0

| # | Change | Gazette / circular |
|---|--------|--------------------|
| 1 | **QQQQ unit code 1-15 characters**, letters/digits only (no spaces, underscores or symbols). Default `MAIN`. | 4.1.a.iii, circular 4.4 |
| 2 | **Serial reset policy per sales journal** (`VAT Serial Reset`): *Continuous* (default - XXXXX continues from the last number even when the month prefix changes), *Restart every January*, *Restart every month*. Invoices, credit notes and debit notes share one counter. | 4.1.a.iv, circular 4.4 |
| 3 | Layout: **Date of Supply** (was "Date of Delivery"), Place of Supply printed only when set, bold **TAX INVOICE** title, amounts with cents (2 decimals). | 1.1, 4.1.c, 4.1.d, 4.1.g |
| 4 | **Disc. % column** printed only when a line has a discount; unit price shown excl. VAT so Qty x Unit Price x (1 - Disc. %) = Amount excl. VAT. | 6.2 |
| 5 | **Foreign currency**: Value of Supply, VAT and Total additionally stated in LKR with the rate used (the document's own booked rate). | circular 4.7 |
| 6 | **Non-VAT buyers**: *Print as Tax Invoice* now defaults from the customer (on only when the customer has a TIN). When off, the same gazette design prints titled **INVOICE / CREDIT NOTE / DEBIT NOTE** without purchaser TIN. Yellow warning banner when a Tax Invoice contains no-VAT / 0% / exempt lines; optional company setting to block posting. | 4.2, circular 4.3 / 4.8 |
| 7 | **Original printed once**: the first PDF of a posted document (Print button, Print menu, Send & Print, e-mail) is the ORIGINAL and is recorded (who/when + chatter). Every later render is automatically **COPY ONLY**, counted and logged. The Print button on a printed document opens the Print Copy wizard. Accounting managers can *Reset Original Print* (reason logged) after a genuine misprint. | audit trail |
| 8 | **Copy set**: optional company setting printing the ORIGINAL once per label (default: Original - Customer / Duplicate - Accounts / Triplicate - Stores / Quadruplicate - Customer Copy) in one PDF. Reprints remain a single COPY ONLY. | client requirement |

Upgrade note: on an *upgrade* from 1.x, existing invoices keep their current *Print as Tax Invoice* value (the new customer-based default applies to new documents) and no existing invoice is flagged as "original printed".

---

## Table of Contents

1. [IRD Requirements Coverage](#1-ird-requirements-coverage)
2. [Features](#2-features)
3. [Document Types](#3-document-types)
4. [Invoice Numbering Format](#4-invoice-numbering-format)
5. [Requirements & Dependencies](#5-requirements--dependencies)
6. [Installation](#6-installation)
7. [Configuration](#7-configuration)
8. [Per-Invoice Fields](#8-per-invoice-fields)
9. [Printing & Reprinting](#9-printing--reprinting)
10. [Security & Compliance Hardening](#10-security--compliance-hardening)
11. [Module Structure](#11-module-structure)
12. [Known Issues & Troubleshooting](#12-known-issues--troubleshooting)
13. [Disabling & Uninstalling](#13-disabling--uninstalling)
14. [Release Notes](#14-release-notes)

---

## 1. IRD Requirements Coverage

The gazette Annexure I specifies the following mandatory fields and behaviours. Each is implemented as a concrete feature in this module.

| Clause | Gazette Requirement | Implementation |
|--------|---------------------|----------------|
| 1.1–1.2 | Document prominently titled "Tax Invoice" | Bold, bordered title box. Automatically switches to "Tax Credit Note" / "Tax Debit Note" by document type; "INVOICE" / "CREDIT NOTE" / "DEBIT NOTE" for buyers that are not VAT registered. |
| 2.1 | Supplier details: TIN, name, address, telephone | Rendered from `res.company` - VAT/TIN, name, street, city, state, ZIP, phone. |
| 3.1 | Purchaser details: TIN, name, address, telephone | Rendered from the invoice's `partner_id`. Purchaser TIN row printed on Tax Invoices only. |
| 4.1.a | Invoice serial number - format `YYMMM_QQQQ_XXXXX`, ≤ 40 characters, no spaces | Custom sequence generator overriding `sequence.mixin`; QQQQ 1-15 alphanumerics; one counter per journal + unit code, shared by invoices / credit notes / debit notes, with a per-journal reset policy (continuous by default, yearly or monthly). |
| 4.1.b | Date of Invoice, `MM/DD/YYYY` | Formatted via `strftime('%m/%d/%Y')`. |
| 4.1.c | Place of Supply | Custom field `l10n_lk_place_of_supply` on `account.move`; defaults to company city, editable per invoice; optional - printed only when set. |
| 4.1.d | Date of Supply, `MM/DD/YYYY` | Uses Odoo's built-in `taxable_supply_date` field, always displayed for LK VAT invoices. |
| 4.1.e–f | Description of Supply, Quantity, Unit of Measure | Invoice line `name`, `quantity`, `product_uom_id`. Sections and note lines rendered distinctly. |
| 4.1.g | Value of Supply: net, VAT amount, total, total in words - **stated in LKR with cents (2 decimal places)**, per the gazette amendment superseding the original whole-rupee rule | Totals section: *Total Value of Supply*, *VAT Amount (@ X%)*, *Total Amount including VAT*, *Total Amount in words* (optional, on by default). All amounts shown at full precision, matching the line items - no rounding applied. |
| 4.1.h | Mode of Payment | Selection field `l10n_lk_mode_of_payment` with seven gazette-specified options. |
| 5.1 | Additional information of the supply | Rich-text "Additional Information" box on the printed report (from invoice narration/notes). |
| 4.2 / circular 4.8 | Tax Invoice includes VAT-taxable supplies only | Warning banner on the invoice form for lines without VAT; optional company setting blocks posting. |
| circular 4.7 | Foreign-currency invoices also stated in LKR | Extra LKR rows (value of supply, VAT, total) with the rate used. |
| 6.2 | Supplier retains a duplicate marked "Duplicate"; reprints must be auditable | "Print Copy" button issues a **COPY ONLY** reprint, requires a reason, logs to chatter, and increments a copy counter. |

---

## 2. Features

### 2.1 Gazette Sequence Numbering

Invoices, credit notes, and debit notes each receive an independent serial number in the format `YYMMM_QQQQ_XXXXX`. The counter resets every calendar month and is scoped to the Sales journal's unit code. See [Invoice Numbering Format](#4-invoice-numbering-format) for full details.

### 2.2 Dedicated Print Layout

A redesigned A4 QWeb report (`report_vat_invoice.xml`) with:

- Independent bordered boxes for every information field.
- A prominent, centered document title with a double border.
- Gray muted labels (9 pt) and bold dark values (10 pt).
- A five-column line-items table with section/note line support.
- A two-row totals section: net value, VAT amount at the configured rate, grand total - all stated in LKR with cents (2 decimal places), matching the line items.
- Amount in words (optional, on by default) and Mode of Payment boxes.
- An optional signature box (configurable name, designation, and blank line for wet signature).
- A repeating page footer on every page showing page numbers and optional company footer text.
- An optional company logo in the top-left corner.
- A **COPY ONLY** circular stamp badge (red, rotated) for reprints.
- Reference to the original invoice number and date on Credit Notes and Debit Notes.

### 2.3 VAT Layout Designer

A three-tab wizard at **Settings → Invoicing → Sri Lanka VAT Compliance → Configure VAT Invoice Layout** to customise the invoice appearance without touching code:

| Tab | Setting | Default |
|-----|---------|---------|
| Layout | VAT Invoice Layout (template selector) | Gazette Default |
| Layout | Show Logo | Off |
| Layout | VAT Rate (%) | 18.00 |
| Layout | Show Total Amount in Words | On |
| Signature | Print Blank Signature Box | Off |
| Signature | Authorized Signatory Name | - |
| Signature | Authorized Signatory Designation | - |
| Footer | Invoice Footer Text | - |

### 2.4 Company-Level Kill Switch

`l10n_lk_vat_enabled` on `res.company` acts as a per-company toggle. When disabled, all gazette-specific behaviour - numbering, layout, extra fields - is bypassed and standard Odoo invoicing operates normally. Safe to install in multi-company databases where only some companies are Sri Lanka VAT-registered.

### 2.5 COPY ONLY Reprint Audit Trail

Every reprint issued through the **Print Copy** button:

- Requires the user to enter a **reason** before proceeding.
- Overlays a red **COPY ONLY** circular stamp on the printed PDF so originals and copies can never be confused.
- Posts a **permanent chatter message** on the invoice recording: who issued the copy, when, and why.
- Increments the `l10n_lk_copy_count` counter, visible as a read-only field on the invoice form once at least one copy has been issued.

### 2.6 Tax Invoice vs. plain Invoice (non-VAT buyers)

`l10n_lk_print_as_tax_invoice` on `account.move` is computed from the customer: **On** when the commercial partner has a Tax ID (TIN), **Off** otherwise. It follows the customer while the document is in draft, can be overridden by the user, and is frozen once the document is posted (and read-only once the original is printed).

| Toggle | Printed document (same gazette design in both cases) |
|--------|------------------------------------------------------|
| On  | TAX INVOICE / TAX CREDIT NOTE / TAX DEBIT NOTE, with Purchaser's TIN |
| Off | INVOICE / CREDIT NOTE / DEBIT NOTE, without Purchaser's TIN |

All entry points - in-form **Print**, cog-wheel **Print** menu, **Send & Print** / e-mail - render the gazette design for every LK VAT sales document. The toggle never affects the serial number.

### 2.6.1 Original / COPY ONLY lock and copy set

See [Printing & Reprinting](#9-printing--reprinting).

### 2.7 Global UTF-8 PDF Fix

Patches `ir.actions.report._build_wkhtmltopdf_args` to pass `--encoding utf-8` to every PDF report in the database. This corrects a known wkhtmltopdf/Qt bug that corrupts multi-byte characters (e.g. en-dashes, superscripts) when HTML is loaded via `file://` without an HTTP `Content-Type` header.

---

## 3. Document Types

### 3.1 Tax Invoice (`out_invoice`)

The standard customer invoice for every taxable supply of goods or services.

- **Title printed:** TAX INVOICE
- **Numbering:** `YYMMM_QQQQ_XXXXX`, counter shared with credit/debit notes of the same journal (see [section 4](#4-invoice-numbering-format)).
- **Original Invoice fields:** not shown.
- **Compliance note:** this is the document the purchaser is legally entitled to receive. Use **Print Copy** (not a second normal print) whenever a duplicate is needed after the original has been issued.

### 3.2 Tax Credit Note (`out_refund`)

Issued against a posted Tax Invoice to reduce the amount owed.

- **Title printed:** TAX CREDIT NOTE
- **Numbering:** shares the journal's gazette counter with Tax Invoices and Debit Notes (unique serial per journal).
- **Original Invoice fields:** prints the original Tax Invoice number (`reversed_entry_id.name`) and date so the credit note is traceable to the specific supply it adjusts.

### 3.3 Tax Debit Note (`out_invoice` with `debit_origin_id`)

Issued against a posted Tax Invoice to increase the amount owed.

- **Title printed:** TAX DEBIT NOTE
- **Numbering:** shares the journal's gazette counter with Tax Invoices and Credit Notes.
- **Original Invoice fields:** prints the original Tax Invoice number (`debit_origin_id.name`) and date.
- **How to create:** use Odoo's standard **Add Debit Note** action. This module adds gazette numbering and layout on top - no separate menu or wizard is introduced.

### 3.4 Copies & Reprints

A controlled mechanism to reprint a posted document without creating a new sequence number.

- **Entry point:** the **Print Copy** button, visible only on posted customer invoices, credit notes, and debit notes when VAT compliance is enabled.
- **Process:**
  1. User clicks **Print Copy** and enters a mandatory reason.
  2. The system increments `l10n_lk_copy_count` on the move.
  3. A permanent chatter entry is posted: user, timestamp, reason, and running copy number.
  4. The PDF is generated with the original sequence number, overlaid with a red **COPY ONLY** stamp.
- **What it does not do:** it does not re-trigger accounting entries, does not change copy counters on related documents, and does not consume a new gazette sequence number.

### 3.5 Document Type Summary

| | Tax Invoice | Tax Credit Note | Tax Debit Note | Copy / Reprint |
|---|---|---|---|---|
| Sequence counter | Shared per journal | Shared per journal | Shared per journal | No - reuses original |
| Shows Original Invoice No. / Date | - | Yes | Yes | Inherits from source |
| COPY ONLY stamp | Every render after the original | Every render after the original | Every render after the original | Always |
| Chatter audit log | Original + every copy | Original + every copy | Original + every copy | Always |

---

## 4. Invoice Numbering Format

```
YYMMM_QQQQ_XXXXX
```

| Segment | Meaning | Example |
|---------|---------|---------|
| `YY` | Last two digits of the invoice year | `26` |
| `MMM` | First three letters of the invoice month, uppercase | `JAN` |
| `QQQQ` | 1-15 letters/digits identifying the unit/branch (configured per journal, default `MAIN`) | `HEAD`, `BR03` |
| `XXXXX` | Numeric running counter (no padding), reset per the journal's policy | `1` |

**Example (gazette):** `26JUL_BR03_1`

**Key behaviours:**

- The counter is **shared across document types** within the same journal and month. Tax Invoices, Tax Credit Notes, and Tax Debit Notes all draw from one monotonically-increasing counter, because Odoo's `(name, journal_id)` unique index prevents any two posted documents from carrying the same serial number. This guarantees uniqueness while preserving the gazette format.
- **Reset policy** (`VAT Serial Reset` on the Sales journal):
  - *Continuous* (default, as the gazette prescribes): `26SEP_BR03_41` is followed by `26OCT_BR03_42`.
  - *Restart every January*: `26DEC_BR03_310` → `27JAN_BR03_1`.
  - *Restart every month*: `26SEP_BR03_41` → `26OCT_BR03_1`.
- The next number is the highest serial already used by the journal + unit within the policy period (+1). Continuous/yearly counters serialise number assignment per journal (row lock on the journal) so two concurrent postings in different months can never issue the same number.
- The `QQQQ` unit code is configured on the **Sales Journal** (`l10n_lk_vat_unit_code`). All Sales journals must have a unit code before enabling VAT compliance - the system will block both the journal save and the company-level toggle if this is missing.
- The full serial never contains spaces and stays well under the 40-character limit (max 6 + 15 + 1 + digits).

---

## 5. Requirements & Dependencies

| Item | Requirement |
|------|-------------|
| Odoo version | 19.0 |
| Python | 3.10+ (no additional packages beyond Odoo core) |
| Odoo modules | `account`, `account_debit_note`, `l10n_lk` |
| System binary | `wkhtmltopdf 0.12.5` (patched-Qt build, as recommended by Odoo) |

---

## 6. Installation

### 6.1 File Placement

Copy or symlink the `l10n_lk_vat` directory into any directory listed in your `addons_path`.

### 6.2 Server Restart & Module Install

```bash
# Option A - command line install
./odoo-bin -d <database> -i l10n_lk_vat --stop-after-init

# Option B - GUI install
# 1. Restart the Odoo server
# 2. Enable developer mode: Settings → General Settings → Developer Tools → Activate
# 3. Apps → Update Apps List
# 4. Search for "Sri Lanka VAT Invoice Compliance" and click Install
```

No demo data, default sequences, or default configuration records are created on installation. Every company must be explicitly configured before gazette invoicing is active.

### 6.3 Running the Test Suite

All tests are tagged `post_install`. Use `-u` (update) to trigger them - `-i` (install) is a no-op when the module is already installed.

```bash
# Run all l10n_lk_vat tests
./odoo-bin -d <database> --test-enable --test-tags l10n_lk_vat -u l10n_lk_vat --stop-after-init

# Run a specific test file by module path
./odoo-bin -d <database> --test-enable --test-tags /l10n_lk_vat/tests/test_sequence.py -u l10n_lk_vat --stop-after-init

# Run a single test class
./odoo-bin -d <database> --test-enable --test-tags /l10n_lk_vat/tests/test_copy.py:TestL10nLkCopy -u l10n_lk_vat --stop-after-init

# Run a single test method
./odoo-bin -d <database> --test-enable --test-tags /l10n_lk_vat/tests/test_fields.py:TestL10nLkFields.test_vat_rate_negative_raises -u l10n_lk_vat --stop-after-init
```

| Test file | What it covers |
|-----------|---------------|
| `tests/test_sequence.py` | Gazette sequence format, monthly reset, counter isolation per document type |
| `tests/test_copy.py` | COPY ONLY counter, wizard guards, copy-mode context bypass security fix |
| `tests/test_fields.py` | Field defaults, VAT rate constraints, journal unit-code constraint, wizard write-through |
| `tests/test_printing.py` | Print-as-Tax-Invoice toggle redirect at all three entry points: Print button, `report_action()`, and `_pre_render_qweb_pdf` (the cog-wheel menu/Send wizard chokepoint) |

> **Tip:** use `-d test_<yourdb>` (a throwaway database) so test data does not pollute your production instance.

---

## 7. Configuration

All steps below must be completed **in order** before posting a gazette invoice.

### 7.1 Set the Unit Code on Sales Journals

This step must be done **before** enabling VAT compliance (the system enforces this order).

1. Go to **Accounting → Configuration → Journals**.
2. Open each **Sales** journal used to issue Tax Invoices.
3. Under the journal settings, set **VAT Unit Code (QQQQ)** - e.g. `HEAD`, `BR01`, `SALES`. 1 to 15 letters/digits, no spaces/underscores. Also choose the **VAT Serial Reset** policy next to it (default *Continuous*).

> This field is **mandatory** for all Sales journals once VAT compliance is enabled. The system will block saving a journal without it, and will block enabling VAT compliance if any existing Sales journals are missing it.

### 7.2 Enable VAT Compliance for the Company

1. Go to **Settings → Invoicing / Accounting**.
2. Under **Sri Lanka VAT Compliance**, toggle **Enable Sri Lanka VAT Compliance** on.
3. Click **Save**.

This is a per-company setting. Other companies in the same database are unaffected until you enable it for them individually.

### 7.3 Configure the Invoice Layout

1. Go to **Settings → Invoicing / Accounting → Sri Lanka VAT Compliance**.
2. Click **Configure VAT Invoice Layout**.

The wizard has three tabs:

#### Tab 1 - Layout

| Setting | Description | Default |
|---------|-------------|---------|
| **VAT Invoice Layout** | The layout template to use. Currently only *Gazette Default* is available. | Gazette Default |
| **Show Logo** | Display the company logo (from the standard document layout) in the top-left corner of the invoice. The gazette does not require a logo. | Off |
| **VAT Rate (%)** | The current VAT rate printed in the label *"VAT Amount (Total Value of Supply @ X%)"*. Update this whenever the gazette rate changes. Must be between 0 and 100. | 18.00 |
| **Show Total Amount in Words** | Print the total amount spelled out in words below the totals table. | On |

#### Tab 2 - Signature

| Setting | Description | Default |
|---------|-------------|---------|
| **Print Blank Signature Box** | Print a blank line with a border at the bottom-right of every invoice for a wet signature. | Off |
| **Authorized Signatory Name** | Name printed above the "Authorized Signatory" line (visible only when the signature box is on). | - |
| **Authorized Signatory Designation** | Job title printed below the signatory name, e.g. *Finance Manager* (visible only when the signature box is on). | - |

#### Tab 3 - Footer

| Setting | Description |
|---------|-------------|
| **Invoice Footer Text** | Free-form text printed at the bottom-left of every VAT invoice on every page, alongside the page number. Typically used for bank details, account numbers, or payment terms. |

Click **Save** to apply changes immediately to all future prints.

---

## 8. Per-Invoice Fields

The following fields appear on each customer invoice, credit note, or debit note when VAT compliance is enabled for the company.

| Field | Location on Form | Description |
|-------|-----------------|-------------|
| **Place of Supply** | Below *Date of Taxable Supply* | Optional. Location from which goods or services are delivered. Defaults to the company's city; clear it to omit the box from the print. |
| **Mode of Payment** | Other Info → Invoice tab, above *Bank Account* | The expected or actual form of payment. Options: Cash, Bank Transfer, Cheque, Credit Card, Debit Card, Mobile Payment, Online Payment. |
| **Additional Information** | Notes / narration field | Rich-text field printed in the *Additional Information* section of the gazette invoice. |
| **Date of Supply** | Invoice tab | Odoo's built-in `taxable_supply_date` field, always shown for LK VAT invoices. Printed as the gazette *Date of Supply* (falls back to the invoice date). |
| **Print as Tax Invoice** | Other Info → Invoice tab | Defaults from the customer's TIN. On: TAX INVOICE with purchaser TIN. Off: same design titled INVOICE, no purchaser TIN. Does not affect the serial number. |
| **Original Printed / On / By** | Other Info → Sri Lanka VAT | Read-only, tracked. Set by the first PDF render of the posted document. |
| **COPY ONLY Reprints** | Other Info → Sri Lanka VAT | Read-only counter of COPY ONLY renders. |
| *(warning banner)* | Top of the form | Yellow banner when a Tax Invoice has lines without VAT (gazette 4.2). |

---

## 9. Printing & Reprinting

### 9.1 Original print

The **first** PDF rendered for a posted LK VAT document is the ORIGINAL, whichever path produced it: the in-form **Print** button, the cog-wheel **Print → Invoice PDF** menu, **Send & Print** (and the e-mail it sends), or any e-mail template / API call. The module records *Original Printed*, *On*, *By* and posts "ORIGINAL printed via <path> by <user>" to the chatter.

When the **copy set** is enabled (VAT Layout wizard → *Copies* tab), the original PDF contains one copy per label, each label printed under the title (default: Original - Customer, Duplicate - Accounts, Triplicate - Stores, Quadruplicate - Customer Copy).

Draft documents print as previews and never consume the original.

### 9.2 Every later render is COPY ONLY

- Clicking **Print** on a document whose original was printed opens the **Print Copy** wizard (reason required) instead of printing.
- Any other later render (Print menu, a new Send & Print, e-mail template) is automatically stamped **COPY ONLY**, increments the copy counter and logs "Reprint as COPY ONLY via <path> by <user>".
- COPY ONLY reprints always render a single copy (no copy set).
- Downloading the PDF that Odoo already stored on the invoice (Send & Print attachment) returns that original file unchanged - that is not a re-render.

### 9.3 Print Copy wizard

1. Open a **posted** customer invoice, credit note, or debit note and click **Print Copy** (or **Print** once the original is printed).
2. Enter a mandatory **reason** and click **Generate COPY ONLY**.

The wizard increments the counter and logs the reason; the following render consumes a one-time server-side token so it is not logged twice.

### 9.4 Reset Original Print (misprints)

Accounting managers (`account.group_account_manager`) see **Reset Original Print** on printed documents. A reason is required; the previous original printer/time and the reason are logged. The next render is the ORIGINAL again.

### 9.5 Document routing

Every LK VAT sales document (Tax Invoice or plain Invoice) uses the gazette design on all print paths. Odoo's global "Invoice PDF" action is not modified - non-LK companies are unaffected.

---

## 10. Security & Compliance Hardening

The following server-side protections are built into this module.

| Protection | Detail |
|------------|--------|
| **Original / COPY decision is server-side** | `_pre_render_qweb_pdf` decides ORIGINAL vs COPY ONLY from the document's own fields and passes the decision to the template through a per-transaction server-side dict, never through the request context. A forged `l10n_lk_vat_copy_mode` in a report URL is ignored unless the Print Copy wizard has just armed its one-time token; it can neither fake a COPY on an unprinted document nor skip the audit log on a printed one. |
| **Reset is manager-only** | `l10n_lk_reset_original_print` checks `account.group_account_manager` server-side (RPC-safe) and requires a reason. |
| **Copy wizard guards** | `action_generate_copy` enforces server-side that the invoice is posted and belongs to an LK VAT Sales journal, regardless of how the wizard is invoked (UI or direct RPC). |
| **Layout wizard company isolation** | The layout wizard rejects writes targeting a company outside the current user's `company_ids`, preventing multi-company privilege escalation via direct RPC. |
| **VAT rate validation** | The VAT rate is constrained to 0–100%. Values outside this range are rejected with a validation error. |
| **Journal pre-flight on company toggle** | Enabling `l10n_lk_vat_enabled` on a company is blocked if any existing Sales journal for that company is missing a VAT Unit Code. This prevents silent fallback to the `HEAD` default on pre-existing journals. |
| **Narration HTML containment** | The Additional Information section renders narration HTML (sanitized by Odoo on write) inside a CSS-isolated container (`overflow: hidden; position: relative`) to limit any layout impact from residual inline styles. |
| **UTF-8 encoding deduplication** | The `--encoding utf-8` argument is added only once per wkhtmltopdf invocation, guarding against duplicate flags if another module or a future Odoo version introduces the same argument. |

---

## 11. Module Structure

```
l10n_lk_vat/
├── hooks.py                     # post_init_hook - backfills new fields on fresh installs into populated DBs
├── models/
│   ├── res_company.py           # Kill switch, layout settings, VAT rate, security constraints
│   ├── account_journal.py       # QQQQ unit code (1-15 alnum), serial reset policy, constraints
│   ├── account_move.py          # Sequence overrides + reset policy, gazette fields, print routing, original/copy lock
│   ├── account_move_line.py     # Unit price excl. VAT helper for the discount column
│   ├── ir_actions_report.py     # wkhtmltopdf UTF-8 fix, margins, gazette redirect, ORIGINAL/COPY chokepoint
│   └── res_config_settings.py   # Related field for the settings page toggle
├── wizard/
│   ├── l10n_lk_vat_layout_wizard.py    # Layout designer wizard (3-tab settings form)
│   ├── l10n_lk_copy_invoice.py         # Print Copy reason dialog and server-side guards
│   └── l10n_lk_reset_original_print.py # Manager-only Reset Original Print (reason logged)
├── report/
│   ├── report_vat_invoice.xml          # Gazette-format QWeb report template
│   └── report_actions.xml              # Report action records, A4 paper format definition
├── views/
│   ├── account_move_views.xml          # Form view additions (Print Copy button, extra fields)
│   ├── account_journal_views.xml       # VAT Unit Code field on journal form
│   ├── res_config_settings_views.xml   # Sri Lanka VAT Compliance block in Accounting settings
│   └── vat_layout_wizard_views.xml     # Layout designer wizard form and action
├── wizard/
│   └── l10n_lk_copy_invoice_views.xml  # Print Copy + Reset Original Print dialogs and actions
├── security/
│   └── ir.model.access.csv             # Model access rules (accountant + manager groups)
├── tests/
│   ├── common.py                        # Shared test setup
│   ├── test_sequence.py                 # Gazette sequence generation and isolation tests
│   ├── test_copy.py                     # COPY ONLY counter, wizard, and security guard tests
│   ├── test_fields.py                   # Field defaults, constraints, and wizard write-through tests
│   ├── test_printing.py                 # Gazette redirect at all entry points
│   └── test_gazette_2481.py             # 2.0: reset policies, layout, discount, FX, non-VAT, original lock, copy set
├── CHANGELOG.md
└── __manifest__.py
```

---

## 12. Known Issues & Troubleshooting

### Garbled characters in PDF (e.g. `ftÂ³` instead of `ft³`)

This is a known wkhtmltopdf/Qt bug: when HTML is loaded from `file://` without an HTTP `Content-Type` header, the encoding is mis-detected as Latin-1. This module patches `ir.actions.report._build_wkhtmltopdf_args` to force `--encoding utf-8` on **every** PDF report in the database. If garbled characters persist, confirm your wkhtmltopdf binary is the Odoo-recommended patched-Qt build (`wkhtmltopdf 0.12.5 (with patched qt)`).

### "Configure Document Layout" wizard appears instead of the PDF

Fixed by overriding `action_print_pdf` on `account.move` to bypass Odoo's standard document-layout configurator for gazette-format invoices. This wizard is irrelevant for our template (which does not use `web.external_layout`).

### Journal save fails with "A VAT Unit Code (QQQQ) is required"

Set the **VAT Unit Code** on the Sales journal before saving. See [Set the Unit Code on Sales Journals](#71-set-the-unit-code-on-sales-journals).

### "Cannot enable Sri Lanka VAT Compliance: the following Sales journals have no VAT Unit Code"

One or more Sales journals already in the database are missing a unit code. Set the **VAT Unit Code** on each listed journal, then retry enabling VAT compliance on the company.

### Sequence shows the wrong month prefix

The prefix is derived from the invoice's `invoice_date` / `date` field, not from the date of the previous invoice. If the prefix looks wrong, verify that the invoice date is set correctly before posting. The prefix is locked at the moment the sequence number is assigned.

### Huge blank space at the top of the printed PDF

This should not occur via any normal printing path: `ir.actions.report._pre_render_qweb_pdf` redirects every call that would otherwise render the standard `account.account_invoices` template to the gazette template for every LK VAT sales document. If you still see this, confirm the invoice qualifies under [`_is_l10n_lk_vat_sequence`](#4-invoice-numbering-format) (company kill switch enabled, Sales journal, invoice or credit note).

### Send & Print e-mails the whole copy set

When the copy set is enabled and the original is produced by Send & Print, the stored/e-mailed PDF is the full original set (all labels). Print the original set from the Print button first if only one copy should be e-mailed - the later Send & Print will then attach a single COPY ONLY.

---

## 13. Disabling & Uninstalling

### Temporarily disabling for a company

Turn off **Enable Sri Lanka VAT Compliance** in Settings → Invoicing for that company. All gazette-specific behaviour (numbering, layout, extra fields) is bypassed immediately. Standard Odoo invoicing resumes for that company. Other companies are not affected.

### Full uninstall

Uninstall from **Apps**. This drops all custom fields (`l10n_lk_place_of_supply`, `l10n_lk_mode_of_payment`, `l10n_lk_copy_count`, `l10n_lk_vat_unit_code`, and all `res.company` layout fields) along with their stored data.

> **Warning:** uninstalling after gazette invoices have been posted is **not recommended**. The custom sequence numbers remain on the posted invoices, but the fields that store place of supply, mode of payment, copy count, and layout settings will be permanently lost.

---

## 14. Release Notes

### 19.0.2.0.0 - October 2026 (Gazette 2481/22 alignment)

See [What's new](#0-whats-new-in-190200) and `CHANGELOG.md`.


### 19.0.1.0.0 - 19 June 2026 (Initial Release)

First public release targeting Odoo 19 and IRD Gazette Extraordinary No. 2481/22, Friday, March 27, 2026.

**Sequence & Numbering**
- Gazette `YYMMM_QQQQ_XXXXX` serial number auto-assigned on post (Clause 4.1.a)
- Monthly counter reset, scoped per journal unit code
- Shared monotonically-increasing counter across Tax Invoices, Credit Notes, and Debit Notes within the same journal (guarantees uniqueness while preserving gazette format)

**PDF Report**
- Dedicated A4 QWeb report for Tax Invoice, Tax Credit Note, and Tax Debit Note
- All IRD-required fields in independently bordered boxes
- Dates in `MM/DD/YYYY` format (Clauses 4.1.b, 4.1.d)
- Five-column line-items table with section/note line support
- Totals in LKR with cents (2 decimal places), per the amended Clause 4.1.g
- Total amount in words - optional, toggleable per company (on by default)
- Repeating page footer with page numbers on every page
- Red **COPY ONLY** circular stamp on reprints (Clause 6.2)
- Original invoice reference block on Credit Notes and Debit Notes

**VAT Layout Designer**
- Three-tab wizard: Layout, Signature, Footer
- Toggle logo, configure VAT rate, signatory name/designation, footer text, total-in-words visibility

**Printing**
- Per-invoice **Print as Tax Invoice** toggle (default on) - lets invoices to non-VAT-registered purchasers fall back to Odoo's standard layout; single source of truth for the Print button, the cog-wheel Print menu, and the Send & Print wizard
- Odoo's global "Invoice PDF" action is never modified - non-LK VAT companies in the same database are unaffected

**Fields**
- Place of Supply - defaults to company city, editable per invoice (Clause 4.1.c)
- Mode of Payment - seven gazette-specified options (Clause 4.1.h)
- Taxable Supply Date always visible for LK VAT documents (Clause 4.1.d)

**Audit & Compliance**
- COPY ONLY reprint requires reason, logs to chatter, increments copy counter
- Journal unit code constraint blocks enabling LK VAT without a valid unit code
- Per-company kill switch - safe to install in multi-company databases

**Other**
- Global UTF-8 fix for wkhtmltopdf (`--encoding utf-8` injected on all PDF reports)
- 56 automated tests across sequence, fields, and copy/reprint flows

---

*Developed by Beaver Hub (Pvt) Ltd - [beaver-hub.com](https://beaver-hub.com)*
