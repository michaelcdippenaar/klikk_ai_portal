# Share & Investment Business Context

## Share Lookup Guide

### TM1 listed_share Dimension
- Element names are short share codes: ABG, SBK, NED, APN, etc.
- Attributes: `share_name` (e.g. ABSAGROUP, STANBANK), `company` (e.g. ABSA GROUP LIMITED), `share_name_2`, `share_name_3`, `sector`
- When user says a company name like "Absa", the element is `ABG` with share_name = `ABSAGROUP`
- Use `tm1_find_element` which searches attributes, or better: use `pg_get_share_data(symbol_search)` for fuzzy matching

### PostgreSQL Share Tables
- `financial_investments_symbol`: Master list with symbol (ABG.JO), name, exchange
- `investec_investecjsesharenamemapping`: Maps between Investec share_name and portfolio share_code
- Symbol search works on: symbol, name, share_name, share_name2, share_name3, company, share_code

### Common Share Name Mappings
| Company | TM1 Element | share_name | Symbol | share_code |
|---------|-------------|------------|--------|------------|
| Absa Group Limited | ABG | ABSAGROUP | ABG.JO | ABG |
| Standard Bank Group | SBK | STANBANK | SBK.JO | SBK |

## Dividend Yield Calculation
- Dividend yield = Annual dividends per share / Share price
- TTM (Trailing Twelve Months) yield = sum of last 12 months dividends / current price
- Annual yield = sum of year's dividends / average price for that year
- Use `build_dividend_yield_chart(symbol_search)` for yield over time visualization
- Investec MonthlyPerformance table has pre-calculated TTM dividend_yield per share

## Data Sources for Share Analysis
1. **Current holdings** -> `pg_get_share_data(symbol, include="holdings")` or `build_holdings_report()`
2. **Dividend history** -> `build_dividend_report(symbol)` or `pg_get_share_data(symbol, include="dividends")`
3. **Dividend yield over time** -> `build_dividend_yield_chart(symbol)`
4. **Transaction history** -> `build_transaction_summary(symbol)` or `pg_get_share_data(symbol, include="transactions")`
5. **Price history** -> `pg_get_share_data(symbol, include="prices")`
6. **TM1 planned positions** -> CubeViewer on `listed_share_src_holdings` or `listed_share_pln_forecast`

## Investec Data Notes
- Portfolio snapshots are point-in-time (monthly). Use latest date's row for current holdings.
- Transaction types: Buy, Sell, Dividend, Special Dividend, Foreign Dividend, Dividend Tax, Fee, Broker Fee
- Share prices in ZAR cents for JSE shares (divide by 100 for rand value)
- US/international shares have exchange_rate applied
- MonthlyPerformance has dividend_ttm (trailing 12m total) and dividend_yield (as decimal, multiply by 100 for %)
