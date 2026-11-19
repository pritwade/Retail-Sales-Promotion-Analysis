# Retail Sales, Promotion & Customer Performance Analysis

**Business question:** Which categories, promotions and customer segments drive sales, and where is the data unreliable?

**Data:** dunnhumby *The Complete Journey* (free download from dunnhumby; raw data is not included in this repo): 2,500 households, 102 weeks, 2,595,732 transaction lines, 92,353 products, 36,786,524 display/mailer (causal) rows, 30 campaigns.

**Tools:** DuckDB SQL · Python (pandas, matplotlib) · Excel · Power BI · Word

Built with AI assistance (Claude, by Anthropic) as a mentor and pair programmer. Every figure comes from code run on the real data, and the code is included so it can be re-run.

---

## Headline results

| Area | Result |
|---|---|
| Sales | $8,057,463.08 across 275,903 baskets; average basket $29.20 |
| Category mix | Grocery, Drug GM and Produce = 77.3% of merchandise sales |
| Growth (wk 76–101 vs 24–49) | +6.6% sales: +3.0% more active households per week, +3.6% spend per active household |
| Private label | 21.4% of merchandise sales at $1.66/unit vs $2.42 for national brands |
| Promotions (matched product-store weeks) | Display + mailer: +21.9% units, −8.0% sales value; discount depth 36.2% vs 10.1% when not promoted |
| Coupon campaigns | TypeA household redemption rate 16.0% vs 7.9% (TypeB) and 7.7% (TypeC) |
| Customers (RFM) | Champions + Loyal = 41.5% of households, 71.4% of sales |
| Forecast baseline | 8-week moving average, MAPE 6.79% on a 12-week holdout |
| Data reliability | Promo flags cover 115 of 582 stores (19.3% of sales); demographics cover 801 of 2,500 households; 98.7% of raw units are fuel/misc meter readings |

## Folder contents

| File | What it is |
|---|---|
| `Retail_Analysis_Report.docx` / `.pdf` | 6-page report: objective, method, data quality, KPIs, findings, recommendations, limitations |
| `Retail_Analysis_Workbook.xlsx` | KPI definitions, department × week pivot (SUMIFS), XLOOKUP reconciliation vs SQL (194 checks) |
| `PowerBI_Build_Guide.md` | Tables, star-schema relationships, DAX measures, control totals, 5-page layout |
| `BW_PowerBI_Theme.json` | Black-and-white Power BI theme (View → Themes → Browse for themes) |
| `powerbi_tables.zip` (not in repo, too large) | CSV tables for Power BI (FactSales, DimProduct, DimHousehold, DimWeek, DimStore, campaign tables, forecast, data-quality log) |
| `cleaned_data.zip` (not in repo, too large) | Cleaned tables (CSV + Parquet), `cleaning_log`, `reconciliation`. The deduplicated causal table (36.8M rows, ~285 MB) is left out for size: its promo flags are already on every line of FactSales (`promo_status`), and `python/02_clean.py` rebuilds it |
| `sql/`, `python/`, `report_build/`, `output/charts/` | SQL queries, Python scripts, report builder and the 7 charts. Result CSVs (`output/results/`) are not stored here; the scripts below regenerate them |

## How to reproduce

Raw CSVs go in `data_raw/` (unzip `causal_data.csv` into `data_raw/causal_unzip/`). Then run:

```bash
pip install duckdb pandas matplotlib openpyxl
python3 python/01_profile.py data_raw output/retail.duckdb
python3 python/01b_profile_causal_and_deepdive.py data_raw/causal_unzip/causal_data.csv output/retail.duckdb
python3 python/01c_followups.py output/retail.duckdb
python3 python/02_clean.py output/retail.duckdb output/clean          # fails if totals do not reconcile
python3 python/03_run_sql.py output/retail.duckdb sql output/results  # runs sql/00-08 in order
python3 python/04_forecast.py output/results
python3 python/05_charts.py output/results output/charts
python3 python/06_kpi_definitions.py output/results
python3 python/07_excel.py output/results Retail_Analysis_Workbook.xlsx
python3 python/08_powerbi_exports.py output/retail.duckdb output/results powerbi_tables
python3 python/09_report_facts.py output/retail.duckdb output/results
node report_build/build_report.js output/results/report_facts.json output/charts Retail_Analysis_Report.docx
python3 python/10_verify_report_numbers.py Retail_Analysis_Report.pdf output/results output/clean
```

The last script checks that every number printed in the report exists in a computed output.

## SQL files

| File | Techniques |
|---|---|
| `00_txn_promo.sql` | Join transactions + product + deduplicated causal; promo status per line |
| `01_kpi_overview.sql` | CTEs, headline KPIs, discount depth |
| `02_weekly_trend.sql` | `LAG` week-over-week change, running total, 4-week moving average, department × week |
| `03_department_mix.sql` | Mix, basket penetration, private-label share, `RANK` |
| `04_commodity_rank.sql` | `RANK() OVER (PARTITION BY DEPARTMENT)`, top / growers / decliners |
| `05_repeat_purchase.sql` | Commodity repeat rate, 4-week retention with `LEAD` |
| `06_promotions.sql` | Matched product-store lift (units, sales, gross value), lift by department, discount depth |
| `07_campaigns.sql` | Redemption rate by campaign and type, redeemer vs non-redeemer spend |
| `08_rfm.sql` | `NTILE(5)` RFM scores, segment rules, demographic profile, segment × department |

## Key assumptions

1. **Removed:** only lines with quantity 0, sales 0 and no discount (9,440). Lines with qty 0 / sales 0 but a coupon discount (4,959; $10,328.53) are kept.
2. **Non-merchandise** (KIOSK-GAS, MISC SALES TRAN, MISC. TRANS., COUP/STR & MFG, UNKNOWN) is in total sales but excluded from units and category analysis.
3. **SALES_VALUE is net of retail discount.** This was verified: sales plus retail discount equals the regular shelf price.
4. **Causal data:** "no row" = not promoted, but only inside the 115 causal stores and weeks 9–101. Conflicting duplicates (15,245 keys) are collapsed; promoted if either row is flagged.
5. **Growth:** compares matched windows (weeks 24–49 vs 76–101) because weeks 1–16 are a household ramp-up.
6. **Returns** cannot be measured (no negative rows). **No inventory, cost or margin data**, so no inventory or profitability claims are made.
7. Promotion and campaign results are **descriptive associations, not causal effects**.
