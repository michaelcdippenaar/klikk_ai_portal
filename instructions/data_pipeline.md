# Data Pipeline — Xero → PostgreSQL → TM1

## Overview
Data flows: Xero API → Django (klikk_financials_v4) → PostgreSQL → TM1 (via TI processes)

## Step 1: Xero API Sync
Trigger: APScheduler (XeroTenantSchedule) or manual via ProcessTree

### Metadata (parallel)
- Accounts → `xero_metadata_xeroaccount` (chart of accounts with code, name, type)
- Tracking Categories → `xero_metadata_xerotracking` (cost centers: Property, Event Equipment, Financial Investments)
- Contacts → `xero_metadata_xerocontacts` (customers, suppliers, employees)

### Transaction Sources (sequential — Xero 5-call limit)
- Bank Transactions → `xero_data_xerotransactionsource` (type=BankTransaction)
- Invoices → `xero_data_xerotransactionsource` (type=Invoice)
- Payments → `xero_data_xerotransactionsource` (type=Payment)
- Credit Notes → `xero_data_xerotransactionsource` (type=CreditNote)
- Prepayments → `xero_data_xerotransactionsource` (type=Prepayment)
- Overpayments → `xero_data_xerotransactionsource` (type=Overpayment)
- Manual Journals → `xero_data_xerojournalssource` (journal_type=manual_journal)
- Journals → `xero_data_xerojournalssource` (journal_type=journal)

## Step 2: Journal Processing
`XeroJournalsSourceManager.create_journals_from_xero()` processes raw journals:

1. Parses dates (handles .NET DateTime, ISO, timestamp formats)
2. Resolves accounts by ID (regular) or code (manual journals)
3. Resolves tracking slots: `XeroTenant.get_tracking_slot(TrackingCategoryID)` → slot 1 or 2
4. Inherits contact from transaction source if journal line has none
5. Splits amount into debit (>= 0) and credit (<= 0)
6. Creates `xero_data_xerojournals` entries (one per line item)
7. Sets `processed = True` on source record

## Step 3: Trail Balance Consolidation
`XeroTrailBalance.consolidate_journals()` runs INSERT...SELECT:

```sql
INSERT INTO xero_cube_xerotrailbalance (organisation_id, account_id, year, month, ...)
SELECT organisation_id, account_id, EXTRACT(YEAR FROM date), ...
FROM xero_data_xerojournals
GROUP BY organisation_id, account_id, year, month, contact_id, tracking1_id, tracking2_id
HAVING SUM(amount) != 0
```

- Calculates `fin_year`/`fin_period` from tenant's `fiscal_year_start_month` (default: July = month 7)
- Computes `balance_to_date` (YTD cumulative for balance sheet accounts)
- Supports full rebuild or incremental (only affected periods)

## Step 4: TM1 Import
TI process reads `xero_cube_xerotrailbalance` → `gl_src_trial_balance` cube.

Column mapping:
| PostgreSQL | TM1 Dimension |
|-----------|---------------|
| organisation_id | entity |
| account_id | account |
| year | year |
| month | month |
| contact_id | contact |
| tracking1_id | tracking_1 |
| tracking2_id | tracking_2 |
| amount, debit, credit, tax_amount | measure_gl_src_trial_balance |

## Step 5: TM1 Calculation Layers
- `gl_src_trial_balance` (source, read-only) — imported from PostgreSQL
- `gl_pln_forecast` (planning) — actual = lookup from src; budget/forecast = user-entered
- `gl_rpt_trial_balance` (reporting) — FY-translated, populated by TI process

## Validation & Reconciliation
- `xero_validation_trailbalancecomparison` — compares Xero API report vs DB trail balance
- `xero_validation_profitandlosscomparison` — P&L reconciliation per month
- `reconcile_gl_totals()` — compares TM1 gl_src vs PostgreSQL xero_cube. Tolerance < 1.0

## Scheduling
- `XeroTenantSchedule` — configurable per-tenant: `enabled`, `update_interval_minutes`, `update_start_time`
- Two-phase: update_models (pull API) then process_data (consolidate)
- Logged in `xero_core_xerotaskexecutionlog`

## Event-Driven Sync (Webhooks)
- `WebhookSubscription` — per-tenant webhook config
- `WebhookEvent` — incoming events (INVOICE, CONTACT, etc.)
- Status flow: received → processing → processed/failed
- Can trigger ProcessTrees via Trigger model

## Investec Data Sync
- Bank transactions: `sync_investec_bank_transactions` management command
- JSE portfolio/transactions: CSV import from Investec exports
- Symbol data: `refresh_all_symbols` fetches yfinance data (prices, dividends, fundamentals)
- `sync_investec_symbols` links Investec share names to yfinance symbols

## Key Business Rules
- Entity uses Xero GUIDs, NOT names. Use `tm1_get_element_attributes_bulk("entity")` for aliases.
- BS accounts: balance accumulates YTD. P&L accounts: balance = amount per period.
- Tracking resolved via `XeroTenant.get_tracking_slot(TrackingCategoryID)` → slot 1 or 2
- Fiscal year starts in July (month 7) for all current tenants
- Fiscal periods: Jul=1, Aug=2, ..., Jun=12
