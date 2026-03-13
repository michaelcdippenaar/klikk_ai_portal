"""
Seed global context store with business facts learned from chat sessions.
Run with: cd backend && python scripts/seed_global_facts.py
Requires: VOYAGE_API_KEY set, pgvector available on klikk_bi_etl.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from context_store import is_available, ensure_tables, save_global_context

FACTS = [
    # Share lookup context
    ("TM1 listed_share element names are short codes (ABG, SBK, NED). "
     "The attribute 'share_name' has the full name (ABSAGROUP, STANBANK). "
     "Use pg_get_share_data(symbol_search) to fuzzy-match by company name, symbol, or share code.",
     {"tags": ["share", "TM1", "lookup"]}),

    ("Absa Group Limited is listed on JSE as ABG.JO. TM1 element: ABG. "
     "Investec share_name: ABSAGROUP. Company: ABSA GROUP LIMITED.",
     {"tags": ["share", "JSE", "Absa"]}),

    ("Standard Bank Group Limited is listed on JSE as SBK.JO. TM1 element: SBK. "
     "Investec share_name: STANBANK. Company: STANDARD BANK GROUP LTD.",
     {"tags": ["share", "JSE", "StandardBank"]}),

    # Dividend yield definition
    ("Dividend yield = annual dividends / share price. "
     "TTM yield = sum of last 12 months dividends / current price. "
     "Use build_dividend_yield_chart(symbol) for yield over time visualization. "
     "Investec MonthlyPerformance table has pre-calculated dividend_yield (as decimal).",
     {"tags": ["share", "dividend", "yield", "formula"]}),

    # Investec data sources
    ("Investec Portfolio is a holdings export (point-in-time snapshots: quantity, cost, value, P&L). "
     "Investec Transaction is an activity export (buys, sells, dividends, fees). "
     "Transaction types: Buy, Sell, Dividend, Special Dividend, Foreign Dividend, Dividend Tax, Fee, Broker Fee.",
     {"tags": ["Investec", "data", "portfolio", "transaction"]}),

    # Share price units
    ("JSE share prices are in ZAR cents (e.g. 23992 = R239.92). "
     "When displaying prices to the user, consider dividing by 100 for rand values. "
     "US shares have exchange_rate applied for ZAR conversion.",
     {"tags": ["share", "JSE", "price", "currency"]}),

    # Report builder tools
    ("For share reports, use: build_dividend_report(symbol) for Google Finance-style dividend report, "
     "build_dividend_yield_chart(symbol) for yield over time, "
     "build_holdings_report() for full portfolio, "
     "build_transaction_summary(symbol) for buy/sell/dividend activity. "
     "These return multiple widgets that render as a dashboard.",
     {"tags": ["report", "share", "tools"]}),

    # Widget creation rules
    ("NEVER create chart widgets (BarChart, LineChart, PieChart) with empty props. "
     "Always query the data first, then pass results as xAxis + series with data arrays. "
     "An empty chart renders blank and is useless to the user.",
     {"tags": ["widget", "chart", "rule"]}),
]


def main():
    if not is_available():
        print("Context store not available (VOYAGE_API_KEY not set or pgvector not installed).")
        print("Facts will be available via RAG indexer (instructions/share_business_context.md) instead.")
        return

    ensure_tables()
    print(f"Seeding {len(FACTS)} global facts...")
    for content, meta in FACTS:
        try:
            row_id = save_global_context(content, metadata=meta)
            print(f"  OK (id={row_id}): {content[:80]}...")
        except Exception as e:
            print(f"  FAIL: {e} — {content[:80]}...")
    print("Done.")


if __name__ == "__main__":
    main()
