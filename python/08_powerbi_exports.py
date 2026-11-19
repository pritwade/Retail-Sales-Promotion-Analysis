"""Step 10 - Star-schema table exports for Power BI.
Usage: python3 08_powerbi_exports.py <db_path> <results_dir> <out_dir>"""
import sys, os, duckdb
db, res, out = sys.argv[1:4]; os.makedirs(out, exist_ok=True)
con = duckdb.connect(db); con.execute("SET memory_limit='3GB'")
tables = {
"FactSales": """SELECT household_key, BASKET_ID, DAY, WEEK_NO, STORE_ID, PRODUCT_ID, TRANS_HOUR,
      QUANTITY, UNITS_MERCH, SALES_VALUE, RETAIL_DISC, COUPON_DISC, COUPON_MATCH_DISC,
      SALES_VALUE - RETAIL_DISC - COUPON_MATCH_DISC AS GROSS_VALUE,
      is_merch, is_free_item, is_discount_only_line, in_causal_scope, promo_status
   FROM txn_promo""",
"DimProduct": "SELECT PRODUCT_ID, MANUFACTURER, DEPARTMENT, BRAND, COMMODITY_DESC, SUB_COMMODITY_DESC, CURR_SIZE_OF_PRODUCT, is_merch FROM clean_product",
"DimHousehold": """SELECT r.household_key, r.segment, r.r_score, r.f_score, r.m_score, r.rfm_code,
      r.recency_days, r.frequency AS baskets, r.monetary AS total_sales, r.first_week,
      CASE WHEN d.household_key IS NULL THEN 0 ELSE 1 END AS has_demographics,
      COALESCE(d.AGE_DESC,'Not available') AS AGE_DESC, COALESCE(d.INCOME_DESC,'Not available') AS INCOME_DESC,
      COALESCE(d.HOMEOWNER_DESC,'Not available') AS HOMEOWNER_DESC, COALESCE(d.HH_COMP_DESC,'Not available') AS HH_COMP_DESC,
      COALESCE(d.HOUSEHOLD_SIZE_DESC,'Not available') AS HOUSEHOLD_SIZE_DESC, COALESCE(d.KID_CATEGORY_DESC,'Not available') AS KID_CATEGORY_DESC,
      COALESCE(d.MARITAL_STATUS_CODE,'Not available') AS MARITAL_STATUS_CODE
   FROM r_rfm_household r LEFT JOIN clean_hh_demographic d USING (household_key)""",
"DimWeek": """SELECT WEEK_NO, MIN(DAY) first_day, MAX(DAY) last_day, COUNT(DISTINCT DAY) n_days,
      CASE WHEN WEEK_NO BETWEEN 2 AND 101 THEN 1 ELSE 0 END is_full_week,
      CASE WHEN WEEK_NO <= 16 THEN 1 ELSE 0 END is_ramp_up,
      CASE WHEN WEEK_NO BETWEEN 9 AND 101 THEN 1 ELSE 0 END has_causal_data,
      CASE WHEN WEEK_NO <= 52 THEN 'Year 1 (wk 1-52)' ELSE 'Year 2 (wk 53-102)' END AS year_label,
      CASE WHEN WEEK_NO BETWEEN 24 AND 49 THEN 'Y1 window (wk 24-49)' WHEN WEEK_NO BETWEEN 76 AND 101 THEN 'Y2 window (wk 76-101)' ELSE 'Other' END AS growth_window
   FROM clean_transactions GROUP BY WEEK_NO""",
"DimStore": """SELECT s.STORE_ID, CASE WHEN c.STORE_ID IS NULL THEN 0 ELSE 1 END AS has_causal_data
   FROM (SELECT DISTINCT STORE_ID FROM clean_transactions) s LEFT JOIN (SELECT DISTINCT STORE_ID FROM clean_causal) c USING (STORE_ID)""",
"DimCampaign": "SELECT CAMPAIGN, DESCRIPTION AS campaign_type, START_DAY, END_DAY, ends_after_data FROM clean_campaign_desc",
"FactCampaignTarget": "SELECT household_key, CAMPAIGN FROM clean_campaign_table",
"FactCouponRedemption": "SELECT household_key, DAY, COUPON_UPC, CAMPAIGN, is_multi_campaign_redemption FROM clean_coupon_redempt",
"FactForecast": f"""SELECT WEEK_NO, method, mode, actual, forecast FROM read_csv_auto('{res}/r_forecast_holdout.csv')
   UNION ALL SELECT WEEK_NO, method, 'forward baseline', NULL, forecast FROM read_csv_auto('{res}/r_forecast_forward.csv')""",
"PromoLiftSummary": f"SELECT * FROM read_csv_auto('{res}/r_promo_lift.csv')",
"DataQualityLog": "SELECT * FROM cleaning_log",
}
for name, sql in tables.items():
    con.execute(f"COPY ({sql}) TO '{out}/{name}.csv' (HEADER)")
    n = con.execute(f"SELECT COUNT(*) FROM ({sql})").fetchone()[0]
    print(f"{name}: {n:,} rows")
# control totals for checking the Power BI model
print(con.execute("SELECT ROUND(SUM(SALES_VALUE),2), SUM(UNITS_MERCH), COUNT(DISTINCT BASKET_ID) FROM txn_promo").fetchone())
