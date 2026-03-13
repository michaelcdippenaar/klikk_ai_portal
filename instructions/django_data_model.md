# Django Data Model — klikk_financials_v4

The AI portal queries PostgreSQL tables created by the Django project at `/home/mc/apps/klikk_financials_v4/`. All tables are in the `klikk_financials_v4` database. Table names follow Django's `appname_modelname` convention.

## Apps Overview

| App | Purpose | Key Tables |
|-----|---------|------------|
| xero_core | Tenant config, scheduling, triggers | xero_core_xerotenant, xero_core_trigger, xero_core_processtree |
| xero_metadata | Chart of accounts, contacts, tracking | xero_metadata_xeroaccount, xero_metadata_xerocontacts, xero_metadata_xerotracking |
| xero_data | Raw journals, transaction sources | xero_data_xerojournals, xero_data_xerotransactionsource |
| xero_cube | Consolidated financials | xero_cube_xerotrailbalance, xero_cube_xeropnlbytracking |
| xero_validation | Reconciliation | xero_validation_trailbalancecomparison |
| investec | Bank & JSE data | investec_investecjsetransaction, investec_investecjseportfolio, investec_investecjsesharenamemapping |
| financial_investments | Market data (yfinance) | financial_investments_symbol, financial_investments_pricepoint, financial_investments_dividend |
| planning_analytics | TM1 connection | planning_analytics_tm1serverconfig |
| ai_agent | Knowledge base | ai_agent_knowledgecorpus, ai_agent_systemdocument |

## Xero Core — Tenant & Orchestration

### xero_core_xerotenant
Central organisation record. All Xero data is keyed by tenant.
- `tenant_id` (PK) — Xero org GUID (same as TM1 entity dimension element)
- `tenant_name` — e.g. "Klikk (Pty) Ltd"
- `tracking_category_1_id`, `tracking_category_2_id` — stable tracking category IDs
- `fiscal_year_start_month` — e.g. 7 for July fiscal year
- Method: `get_tracking_slot(tracking_category_id)` → returns 1 or 2

### xero_core_trigger
Event/condition-based triggers for process trees.
- `trigger_type`: condition, schedule, event, custom, outdated_check
- Links to `xero_core_processtree` for execution

### xero_core_processtree
Stores process pipeline definitions as JSON trees.
- `process_tree_data` (JSON) — tree of steps to execute
- Supports dependent_trees (sequential) and sibling_trees (parallel)

### xero_core_xerolastupdate
Tracks last sync timestamp per endpoint per tenant.
- `end_point`: accounts, contacts, tracking_categories, journals, manual_journals, etc.
- Used for incremental delta syncs

### xero_core_xerotaskexecutionlog
Audit log for sync tasks.
- `task_type`: update_models, process_data
- `status`: pending, running, completed, failed, skipped
- `stats` (JSON) — detailed execution metrics

## Xero Metadata — Reference Data

### xero_metadata_xeroaccount
Chart of accounts from Xero. ~382 elements per org.
- `account_id` (PK) — Xero account GUID (same as TM1 account dimension element)
- `code` — account code (e.g. "200", "400")
- `name` — account name (e.g. "Sales", "Cost of Goods Sold")
- `type` — REVENUE, EXPENSE, ASSET, LIABILITY, EQUITY
- `reporting_code`, `reporting_code_name` — Xero reporting categories
- `attr_entry_type`, `attr_occurrence` — custom attributes for TM1

### xero_metadata_xerocontacts
Xero contacts (customers/suppliers). ~1,152 per org.
- `contacts_id` (PK) — Xero contact GUID (same as TM1 contact dimension element)
- `name` — display name (e.g. "CLAUDE AI", "Webstel Projects Pty Ltd")
- `collection` (JSON) — full Xero API response

### xero_metadata_xerotracking
Tracking categories (cost centers/departments).
- `option_id` — unique option ID
- `name` — category name (e.g. "Property", "Event Equipment", "Financial Investments")
- `tracking_category_id` — stable parent category ID
- Maps to TM1 dimensions tracking_1 and tracking_2

## Xero Data — Raw Transactions

### xero_data_xerotransactionsource
Parent documents for journal entries.
- `transaction_source`: BankTransaction, Invoice, Payment, CreditNote, Prepayment, Overpayment
- Links to contact and stores full API response in `collection` (JSON)

### xero_data_xerojournals
Clean, processed journal entries (one row per line item).
- `journal_id` — unique per org
- `account` (FK) → xero_metadata_xeroaccount
- `contact` (FK) → xero_metadata_xerocontacts
- `tracking1`, `tracking2` (FK) → xero_metadata_xerotracking
- `amount`, `debit` (>= 0), `credit` (<= 0), `tax_amount`
- Constraint: debit + credit = amount

### xero_data_xerojournalssource
Raw journal API responses before processing.
- `journal_type`: journal, manual_journal
- `processed` flag — set True after creating XeroJournals entries

## Xero Cube — Consolidated Financials

### xero_cube_xerotrailbalance
**Core fact table** — aggregated balances per account/period/contact/tracking.
- `organisation` (FK) → tenant
- `account` (FK) → xero_metadata_xeroaccount
- `year`, `month` — calendar period
- `fin_year`, `fin_period` — fiscal period (based on tenant's fiscal_year_start_month)
- `contact` (FK), `tracking1` (FK), `tracking2` (FK)
- `amount`, `debit`, `credit`, `tax_amount`
- `balance_to_date` — YTD balance (for balance sheet accounts)

Built by `consolidate_journals()`: INSERT...SELECT from xero_data_xerojournals, grouped by org/account/period/contact/tracking.

### Column → TM1 Dimension Mapping
| PG Column | TM1 Dimension | Notes |
|-----------|---------------|-------|
| organisation_id | entity | Xero org GUIDs |
| account_id | account | Chart of accounts GUIDs |
| year | year | Calendar year |
| month | month | Calendar month name |
| contact_id | contact | Contact GUIDs |
| tracking1_id | tracking_1 | Property, Event Equipment, Financial Investments |
| tracking2_id | tracking_2 | Secondary tracking |
| amount/debit/credit | measure_gl_src_trial_balance | Measures |

## Investec — Bank & JSE Holdings

### investec_investecjsesharenamemapping
Maps between transaction share names and portfolio share codes.
- `share_name` (unique) — e.g. "ABSAGROUP" (from transactions)
- `share_code` (unique) — e.g. "ABG" (from portfolio)
- `company` — e.g. "ABSA GROUP LIMITED"
- `share_name2`, `share_name3` — alternate names
- Links to financial_investments_symbol via symbol.share_name_mapping_id

### investec_investecjsetransaction
Investec JSE transaction export — activity history.
- `date`, `year`, `month`, `day`
- `share_name` — matches sharenamemapping
- `type`: Buy, Sell, Dividend, Special Dividend, Foreign Dividend, Dividend Tax, Fee, Broker Fee
- `quantity`, `value`, `value_per_share`, `value_calculated`
- `dividend_ttm` — trailing 12-month dividend at time of transaction
- `account_number`, `description`

### investec_investecjseportfolio
Investec holdings snapshot — point-in-time positions.
- `date`, `company`, `share_code`
- `quantity`, `currency`, `unit_cost`, `total_cost`
- `price`, `total_value`, `exchange_rate`
- `profit_loss`, `portfolio_percent`, `annual_income_zar`
- Multiple snapshots per share (monthly). Use latest date for current holdings.

### investec_investecjsesharemonthlyperformance
Calculated monthly metrics per share.
- `share_name`, `date`, `dividend_type`, `investec_account`
- `dividend_ttm` — trailing 12-month total dividends
- `closing_price`, `quantity`, `total_market_value`
- `dividend_yield` — as decimal (multiply by 100 for %)

### investec_investecbankaccount
Investec Private Bank accounts.
- `account_id`, `account_number`, `account_name`
- From Investec API: GET /za/pb/v1/accounts

### investec_investecbanktransaction
Bank transactions from Investec API.
- `account` (FK) → investec_investecbankaccount
- `type`: CREDIT, DEBIT
- `status`: POSTED, PENDING
- `amount`, `running_balance`
- `posting_date`, `transaction_date`

## Financial Investments — Market Data (yfinance)

### financial_investments_symbol
Master ticker list.
- `symbol` (unique) — e.g. "ABG.JO", "ASPI", "AAPL"
- `name` — full company name
- `exchange` — e.g. "JNB", "NCM"
- `category` — equity, etf, index, forex
- `share_name_mapping` (OneToOne) → investec_investecjsesharenamemapping

### financial_investments_pricepoint
Daily OHLCV from yfinance.
- `symbol` (FK), `date`
- `open`, `high`, `low`, `close`, `volume`, `adjusted_close`
- JSE prices in ZAR cents

### financial_investments_dividend
Dividend payment history from yfinance.
- `symbol` (FK), `date`, `amount`, `currency`

### financial_investments_split
Stock split events.
- `symbol` (FK), `date`, `ratio`

### financial_investments_symbolinfo
Company metadata snapshot (yfinance ticker.info as JSON).

### financial_investments_financialstatement
Income statements, balance sheets, cash flows.
- `statement_type`: income_stmt, balance_sheet, cash_flow
- `freq`: yearly, quarterly, trailing
- `data` (JSON)

### financial_investments_earningsreport / earningsestimate
Actual earnings and analyst estimates (JSON).

### financial_investments_analystrecommendation / analystpricetarget
Analyst buy/sell/hold recommendations and price targets (JSON).

### financial_investments_ownershipsnapshot
Institutional/insider holdings (JSON).

### financial_investments_newsitem
News articles per symbol.

## AI Agent — Knowledge Base

### ai_agent_knowledgecorpus
Document collections for RAG retrieval.
- `slug`, `name`, `description`, `is_active`

### ai_agent_systemdocument
Documents pinned to agent context.
- `corpus` (FK), `title`, `content_markdown`
- `pin_to_context` — always include in system prompt
- `metadata` (JSON)

### ai_agent_agentsession / agentmessage
Conversation history per tenant/project.

### ai_agent_knowledgechunkembedding
Vector embeddings for document chunks.
- `chunk_text`, `embedding` (JSON list of floats)
- `embedding_model` — model used for embedding
