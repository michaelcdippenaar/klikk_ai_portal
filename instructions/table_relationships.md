# Table Relationships & Join Patterns

## Xero Financial Data Chain

```
xero_core_xerotenant (tenant_id PK)
  ├── xero_metadata_xeroaccount (account_id PK, organisation FK→tenant)
  ├── xero_metadata_xerocontacts (contacts_id PK, organisation FK→tenant)
  ├── xero_metadata_xerotracking (id PK, organisation FK→tenant)
  │
  ├── xero_data_xerotransactionsource (transactions_id, organisation FK→tenant)
  │     └── contact FK→xerocontacts
  │
  ├── xero_data_xerojournalssource (journal_id, organisation FK→tenant)
  │
  ├── xero_data_xerojournals (journal_id PK, organisation FK→tenant)
  │     ├── account FK→xeroaccount
  │     ├── contact FK→xerocontacts
  │     ├── tracking1 FK→xerotracking
  │     ├── tracking2 FK→xerotracking
  │     └── transaction_source FK→xerotransactionsource
  │
  └── xero_cube_xerotrailbalance (id PK, organisation FK→tenant)
        ├── account FK→xeroaccount
        ├── contact FK→xerocontacts
        ├── tracking1 FK→xerotracking
        └── tracking2 FK→xerotracking
```

## Share & Investment Data Chain

```
investec_investecjsesharenamemapping (id PK)
  ├── share_name (unique) — e.g. "ABSAGROUP"
  ├── share_code (unique) — e.g. "ABG"
  ├── company — e.g. "ABSA GROUP LIMITED"
  │
  ├── investec_investecjsetransaction
  │     └── share_name matches sharenamemapping.share_name
  │
  ├── investec_investecjseportfolio
  │     └── share_code matches sharenamemapping.share_code
  │
  ├── investec_investecjsesharemonthlyperformance
  │     └── share_name matches sharenamemapping.share_name
  │
  └── financial_investments_symbol (id PK)
        ├── share_name_mapping OneToOne→sharenamemapping
        ├── symbol — e.g. "ABG.JO"
        │
        ├── financial_investments_pricepoint (symbol FK, date) — daily OHLCV
        ├── financial_investments_dividend (symbol FK, date) — dividend payments
        ├── financial_investments_split (symbol FK, date) — stock splits
        ├── financial_investments_symbolinfo (symbol 1:1) — company info JSON
        ├── financial_investments_financialstatement (symbol FK) — financials JSON
        ├── financial_investments_earningsreport (symbol FK) — earnings JSON
        ├── financial_investments_earningsestimate (symbol 1:1) — estimates JSON
        ├── financial_investments_analystrecommendation (symbol 1:1) — analyst recs
        ├── financial_investments_analystpricetarget (symbol 1:1) — price targets
        ├── financial_investments_ownershipsnapshot (symbol FK) — holders
        └── financial_investments_newsitem (symbol FK) — news articles
```

## Common SQL Join Patterns

### Get share with all identifiers
```sql
SELECT s.symbol, s.name, s.exchange,
       m.share_name, m.share_code, m.company
FROM financial_investments_symbol s
LEFT JOIN investec_investecjsesharenamemapping m
    ON m.id = s.share_name_mapping_id
```

### Get latest holdings with company names
```sql
SELECT DISTINCT ON (p.share_code)
    p.company, p.share_code, p.quantity, p.total_cost,
    p.price, p.total_value, p.profit_loss, p.annual_income_zar
FROM investec_investecjseportfolio p
ORDER BY p.share_code, p.date DESC
```

### Get dividends received for a share
```sql
SELECT t.date, t.type, t.value, t.value_per_share, t.quantity
FROM investec_investecjsetransaction t
WHERE t.share_name = 'ABSAGROUP'
  AND t.type IN ('Dividend', 'Special Dividend', 'Foreign Dividend')
ORDER BY t.date DESC
```

### Get trail balance for an entity/period
```sql
SELECT a.code, a.name, a.type,
       tb.amount, tb.debit, tb.credit, tb.balance_to_date
FROM xero_cube_xerotrailbalance tb
JOIN xero_metadata_xeroaccount a ON a.account_id = tb.account_id
WHERE tb.organisation_id = '41ebfa0e-012e-4ff1-82ba-a9a7585c536c'
  AND tb.year = 2025 AND tb.month = 'Mar'
ORDER BY a.code
```

### Get dividend yield over time
```sql
SELECT EXTRACT(YEAR FROM d.date)::int AS yr,
       SUM(d.amount) AS total_div,
       AVG(p.close) AS avg_price,
       CASE WHEN AVG(p.close) > 0 THEN SUM(d.amount) / AVG(p.close) * 100 END AS yield_pct
FROM financial_investments_dividend d
JOIN financial_investments_pricepoint p ON p.symbol_id = d.symbol_id
    AND EXTRACT(YEAR FROM p.date) = EXTRACT(YEAR FROM d.date)
WHERE d.symbol_id = (SELECT id FROM financial_investments_symbol WHERE symbol = 'ABG.JO')
GROUP BY yr ORDER BY yr
```

## Bank Data

```
investec_investecbankaccount (account_id PK)
  └── investec_investecbanktransaction (id PK)
        ├── account FK→bankaccount
        ├── type: CREDIT, DEBIT
        ├── status: POSTED, PENDING
        └── amount, running_balance
```

## AI Agent Data

```
ai_agent_knowledgecorpus (id PK)
  └── ai_agent_systemdocument (id PK, corpus FK)
        └── ai_agent_knowledgechunkembedding (id PK, system_document FK)

ai_agent_agentproject (id PK)
  └── ai_agent_agentsession (id PK, project FK, organisation FK→tenant)
        ├── ai_agent_agentmessage (id PK, session FK)
        │     └── ai_agent_agenttoolexecutionlog (id PK, message FK)
        └── ai_agent_agentapprovalrequest (id PK, session FK)
```
