# Test Prompts for All Agent Skills & Tools

Use these prompts in the AI Portal chat to verify each tool works correctly.
Mark PASS/FAIL for each and note any issues.

---

## 1. tm1_metadata.py — TM1 Model Exploration

| # | Tool | Test Prompt | Expected |
|---|------|-------------|----------|
| 1.1 | `tm1_list_dimensions` | "List all dimensions in the TM1 model" | Returns user dimension names (account, entity, month, etc.) |
| 1.2 | `tm1_list_cubes` | "List all cubes with their dimensions" | Returns cube names, dimension lists, has_rules flag |
| 1.3 | `tm1_get_dimension_elements` (all) | "Show me all elements in the month dimension" | Returns all month elements (Jan–Dec, All_Month, etc.) |
| 1.4 | `tm1_get_dimension_elements` (leaf) | "Show me only leaf elements in the entity dimension" | Returns only N-level (non-consolidated) entities |
| 1.5 | `tm1_get_dimension_elements` (consolidated) | "Show only consolidated elements in the account dimension" | Returns only C-level rollup elements |
| 1.6 | `tm1_get_element_attributes` | "What attributes does the account dimension have?" | Returns attribute names and types (alias, string, numeric) |
| 1.7 | `tm1_get_element_attribute_value` | "What is the alias attribute of element acc_001 in account dimension?" | Returns the friendly name for acc_001 |
| 1.8 | `tm1_get_element_attributes_bulk` | "Show me the alias for all leaf elements in the entity dimension" | Returns a table of element names → alias values |
| 1.9 | `tm1_list_processes` | "List all TI processes on the server" | Returns process names with parameter signatures |
| 1.10 | `tm1_get_process_code` | "Show me the code for the process ops_gl_import" | Returns prolog/metadata/data/epilog code blocks |
| 1.11 | `tm1_get_cube_rules` | "Show me the rules for the gl_src_trial_balance cube" | Returns rules text or empty if none |
| 1.12 | `tm1_get_hierarchy` | "Show me the hierarchy structure of the account dimension" | Returns parent-child tree |
| 1.13 | `tm1_find_element` | "Find which dimension contains the element 'Klikk_Org'" | Returns matching dimensions with exact/partial matches |
| 1.14 | `tm1_validate_elements` | "Validate these elements for gl_src_trial_balance: 2025, Jul, actual, Klikk_Org, acc_001" | Returns valid/invalid per element with suggestions |

---

## 2. tm1_query.py — TM1 Data Queries

| # | Tool | Test Prompt | Expected |
|---|------|-------------|----------|
| 2.1 | `tm1_query_mdx` | "Run this MDX: SELECT {[version].[actual]} ON 0, {[account].[All_Account].Children} ON 1 FROM [gl_src_trial_balance] WHERE ([year].[2025],[month].[Jul],[entity].[All_Entity],[contact].[All_Contact],[tracking_1].[All_Tracking_1],[tracking_2].[All_Tracking_2],[measure_gl_src_trial_balance].[amount])" | Returns coordinate/value pairs with cell data |
| 2.2 | `tm1_execute_mdx_rows` | "Show me revenue by month for 2025 as a table" | Returns headers + rows in tabular format |
| 2.3 | `tm1_read_view` | "Read the view 'rpt_buy and sell trades' from cube listed_share_src_transactions" | Returns cell data from the named view |
| 2.4 | `tm1_read_view_as_table` | "Read view 'rpt_buy and sell trades' from listed_share_src_transactions as a table" | Returns headers + rows from named view |
| 2.5 | `tm1_get_cell_value` | "Get the single cell value for gl_src_trial_balance at coordinates: 2025, Jul, actual, Klikk_Org, acc_001, All_Contact, All_Tracking_1, All_Tracking_2, amount" | Returns a single numeric value |
| 2.6 | `tm1_list_views` | "List all views for the cashflow_pln_forecast cube" | Returns sorted list of view names |

---

## 3. tm1_rest_api.py — TM1 REST / Admin Tools

| # | Tool | Test Prompt | Expected |
|---|------|-------------|----------|
| 3.1 | `tm1_rest_server_status` | "Check the TM1 server health and version" | Returns product version, server name, session count, thread states |
| 3.2 | `tm1_rest_message_log` | "Show me the last 10 TM1 server log messages" | Returns timestamped log entries |
| 3.3 | `tm1_rest_message_log` (filtered) | "Show me only TM1 error log entries from the last hour" | Returns filtered error-level entries |
| 3.4 | `tm1_rest_transaction_log` | "Show the last 20 transaction log entries" | Returns who-wrote-what audit entries |
| 3.5 | `tm1_rest_transaction_log` (filtered) | "Show transaction log for the gl_src_trial_balance cube" | Returns entries filtered by cube |
| 3.6 | `tm1_rest_active_sessions` | "Who is currently logged into TM1?" | Returns active session list with usernames |
| 3.7 | `tm1_rest_active_threads` | "Show me all active TM1 threads" | Returns thread list, highlights non-idle |
| 3.8 | `tm1_rest_sandbox_list` | "List all sandboxes on the TM1 server" | Returns sandbox names with active/loaded status |
| 3.9 | `tm1_rest_sandbox_create` | "Create a sandbox called 'test_what_if'" | Creates sandbox, returns confirmation |
| 3.10 | `tm1_rest_sandbox_delete` | "Delete the sandbox called 'test_what_if'" | Deletes sandbox, returns confirmation |
| 3.11 | `tm1_rest_execute_view` | "Execute the view 'rpt_buy and sell trades' from listed_share_src_transactions using REST" | Returns cells + tabular data via POST tm1.Execute |
| 3.12 | `tm1_rest_execute_mdx_cellset` | "Execute this MDX via REST and show axis info: SELECT {[version].[actual]} ON 0, {[month].[Jan],[month].[Feb]} ON 1 FROM [gl_src_trial_balance]" | Returns full cellset with axis tuples and ordinals |
| 3.13 | `tm1_rest_write_values` (dry-run) | "Dry-run writing value 100 to gl_src_trial_balance at 2025,Jan,actual,Klikk_Org,acc_001,All_Contact,All_Tracking_1,All_Tracking_2,amount" | Returns dry_run preview, does NOT write |
| 3.14 | `tm1_rest_error_log` | "Show TM1 error log files" | Returns list of error log files with sizes |
| 3.15 | `tm1_rest_cube_info` | "Give me detailed info on the gl_src_trial_balance cube" | Returns dimensions, views, rules preview, last update |

---

## 4. tm1_management.py — TM1 Write / Process Execution

| # | Tool | Test Prompt | Expected |
|---|------|-------------|----------|
| 4.1 | `tm1_run_process` (dry-run) | "Dry-run the TI process ops_gl_import" | Returns process parameters preview, does NOT execute |
| 4.2 | `tm1_run_process` (execute) | "Run the TI process ops_gl_import with confirm=true" | Actually runs the process, returns status |
| 4.3 | `tm1_write_cell` (dry-run) | "Preview writing 500 to gl_src_trial_balance at 2025,Jan,budget,Klikk_Org,acc_001,All_Contact,All_Tracking_1,All_Tracking_2,amount" | Returns preview only |
| 4.4 | `tm1_update_element_attribute` (dry-run) | "Preview updating the alias attribute of acc_001 in account to 'Office Rent'" | Returns preview only |
| 4.5 | `tm1_get_server_info` | "Get TM1 server name and session count" | Returns server_name, active_sessions |

---

## 5. postgres_query.py — PostgreSQL Queries

| # | Tool | Test Prompt | Expected |
|---|------|-------------|----------|
| 5.1 | `pg_list_tables` | "List all tables in the financials database with their sizes" | Returns table names, row counts, sizes |
| 5.2 | `pg_describe_table` | "Describe the structure of the xero_gl_trial_balance table" | Returns column names and data types |
| 5.3 | `pg_query_financials` | "SELECT COUNT(*) FROM xero_gl_trial_balance WHERE year = '2025'" | Returns count result |
| 5.4 | `pg_query_bi` | "List tables in the BI ETL database" | Returns BI ETL table listing |
| 5.5 | `pg_get_xero_gl_sample` | "Show me a sample of Xero GL data for July 2025" | Returns sample rows from Xero GL |

---

## 6. kpi_monitor.py — KPI & Period Tools

| # | Tool | Test Prompt | Expected |
|---|------|-------------|----------|
| 6.1 | `get_current_period` | "What is the current financial period?" | Returns year, month, financial year |
| 6.2 | `list_kpi_definitions` | "List all defined KPIs" | Returns KPI definitions from YAML |
| 6.3 | `get_all_kpi_values` | "Calculate all KPIs for July 2025" | Returns computed values with threshold status |
| 6.4 | `get_kpi_dashboard` | "Show me the KPI dashboard for the current period" | Returns all KPIs for current period |
| 6.5 | `get_gl_summary` | "Show me the GL summary (income, expenses, net profit) for July 2025" | Returns GL totals |
| 6.6 | `add_kpi_definition` (dry-run) | "Add a new KPI called 'Gross Margin %' that calculates gross margin percentage" | Returns preview, does NOT write |
| 6.7 | `remove_kpi_definition` (dry-run) | "Preview removing the KPI with id 'gross_margin_pct'" | Returns preview, does NOT remove |

---

## 7. pattern_analysis.py — Variance & Anomaly Detection

| # | Tool | Test Prompt | Expected |
|---|------|-------------|----------|
| 7.1 | `analyse_gl_variance` | "Compare actual vs budget for GL accounts in July 2025" | Returns top accounts by absolute variance |
| 7.2 | `detect_gl_anomalies` | "Detect any anomalous GL accounts this month compared to the last 12 months" | Returns statistically anomalous accounts |
| 7.3 | `compare_periods` | "Compare GL amounts between June 2025 and July 2025 for Klikk_Org" | Returns account-level deltas |
| 7.4 | `find_unmapped_cashflow_accounts` | "Find GL accounts not mapped in cashflow routing" | Returns unmapped account list |

---

## 8. validation.py — Model Validation & Connectivity

| # | Tool | Test Prompt | Expected |
|---|------|-------------|----------|
| 8.1 | `test_tm1_connection` | "Test the TM1 connection" | Returns server info or error |
| 8.2 | `test_postgres_connections` | "Test both PostgreSQL database connections" | Returns status for both DBs |
| 8.3 | `verify_model_structure` | "Verify that all expected TM1 dimensions and cubes exist" | Returns pass/fail with missing objects |
| 8.4 | `reconcile_gl_totals` | "Reconcile GL totals between TM1 and PostgreSQL for July 2025" | Returns comparison with match/mismatch |

---

## 9. element_context.py — Element RAG & Context Notes

| # | Tool | Test Prompt | Expected |
|---|------|-------------|----------|
| 9.1 | `index_dimension_elements` | "Index all elements in the account dimension for RAG" | Vectorises elements, stores in pgvector |
| 9.2 | `save_element_context` | "Remember that acc_001 in the account dimension is the main office rent account, typically R45K/month" | Saves context note |
| 9.3 | `get_element_context` | "What do we know about acc_001 in the account dimension?" | Returns stored profile and context notes |
| 9.4 | `index_all_key_dimensions` | "Index all key dimensions for RAG lookup" | Vectorises account, entity, cashflow_activity, listed_share, month, version |

---

## 10. web_search.py — Internet Search

| # | Tool | Test Prompt | Expected |
|---|------|-------------|----------|
| 10.1 | `web_search` | "Search for the current South African prime lending rate" | Returns search results with sources |
| 10.2 | `web_search` (specific) | "Search for IFRS 16 lease accounting requirements" | Returns relevant accounting standard info |
| 10.3 | `web_fetch_page` | "Read the full content of https://www.resbank.co.za/en/home/what-we-do/statistics/key-statistics/current-market-rates" | Returns extracted page text |
| 10.4 | `web_search_news` | "Search for recent news about property market in South Africa" | Returns recent news articles |

---

## 11. google_drive.py — Google Drive Integration

| # | Tool | Test Prompt | Expected |
|---|------|-------------|----------|
| 11.1 | `gdrive_list_files` | "List files in my Google Drive root folder" | Returns file names, IDs, types |
| 11.2 | `gdrive_read_document` | "Read the document [pick a known file ID]" | Returns extracted text content |
| 11.3 | `gdrive_index_folder` | "Index all documents from the finance folder into the RAG store" | Downloads, chunks, embeds, stores |

---

## 12. paw_integration.py — Planning Analytics Workspace

| # | Tool | Test Prompt | Expected |
|---|------|-------------|----------|
| 12.1 | `paw_status` | "Check PAW connectivity and version" | Returns PAW/TM1 status |
| 12.2 | `paw_list_books` | "List all available PAW books" | Returns book names |
| 12.3 | `paw_list_views` | "List saved views for gl_src_trial_balance" | Returns view names |
| 12.4 | `paw_list_subsets` | "List subsets for the account dimension" | Returns subset names |
| 12.5 | `paw_open_cube_viewer` | "Open a cube viewer for listed_share_src_holdings" | Renders PAW cube viewer widget in chat |
| 12.6 | `paw_open_dimension_editor` | "Open the dimension editor for the account dimension" | Renders PAW dimension editor widget |
| 12.7 | `paw_open_set_editor` | "Open the set editor for account subsets" | Renders PAW set editor widget |
| 12.8 | `paw_open_book` | "Open PAW book [known book name]" | Renders PAW book widget |
| 12.9 | `paw_open_websheet` | "Open the websheet [known websheet name]" | Renders TM1 Web websheet widget |

---

## 13. widget_generation.py — Dashboard Widgets

| # | Tool | Test Prompt | Expected |
|---|------|-------------|----------|
| 13.1 | `create_dashboard_widget` (table) | "Show me a table of revenue by month for 2025" | Renders a table widget in chat |
| 13.2 | `create_dashboard_widget` (chart) | "Create a bar chart of expenses by account for July 2025" | Renders a chart widget in chat |
| 13.3 | `create_dashboard_widget` (kpi card) | "Create a KPI card showing net profit for July 2025" | Renders a KPI card widget |
| 13.4 | Widget pin | "Pin this widget to the dashboard" (after generating one) | Widget appears on dashboard |

---

## 14. session_review.py — Chat Session Review

| # | Tool | Test Prompt | Expected |
|---|------|-------------|----------|
| 14.1 | `list_chat_sessions` | "List all available chat session logs" | Returns session files with metadata |
| 14.2 | `read_chat_session` | "Read the most recent chat session transcript" | Returns full message/tool/response log |
| 14.3 | `review_chat_session` | "Review the most recent chat session for improvement ideas" | Returns tool usage, errors, suggestions |

---

## Quick Smoke Test (run these 5 prompts to validate core functionality)

1. **"What dimensions are in the TM1 model?"** — tests tm1_metadata
2. **"Show me revenue by month for 2025 as a table"** — tests tm1_query + widget
3. **"Check TM1 server health"** — tests tm1_rest_api
4. **"Test all database connections"** — tests validation
5. **"Open a cube viewer for gl_src_trial_balance"** — tests paw_integration

---

## Test Log

| Date | Tester | # Tested | # Passed | # Failed | Notes |
|------|--------|----------|----------|----------|-------|
|      |        |          |          |          |       |
