-- 01_kpi_overview.sql  : headline KPIs (definitions in KPI_definitions.csv)
CREATE OR REPLACE TABLE r_kpi_overview AS
WITH base AS (SELECT * FROM clean_transactions),
hh_baskets AS (SELECT household_key, COUNT(DISTINCT BASKET_ID) nb FROM base GROUP BY 1)
SELECT
  ROUND(SUM(SALES_VALUE),2)                                             AS total_sales,
  ROUND(SUM(CASE WHEN is_merch=1 THEN SALES_VALUE END),2)               AS merch_sales,
  SUM(UNITS_MERCH)                                                      AS merch_units,
  COUNT(DISTINCT BASKET_ID)                                             AS baskets,
  COUNT(DISTINCT household_key)                                         AS households,
  ROUND(SUM(SALES_VALUE)/COUNT(DISTINCT BASKET_ID),2)                   AS avg_basket_value,
  ROUND(SUM(SALES_VALUE)/COUNT(DISTINCT household_key),2)               AS sales_per_household,
  ROUND(COUNT(DISTINCT BASKET_ID)*1.0/COUNT(DISTINCT household_key),1)  AS baskets_per_household,
  ROUND(100.0*(SELECT COUNT(*) FROM hh_baskets WHERE nb>=2)/(SELECT COUNT(*) FROM hh_baskets),2) AS pct_hh_2plus_baskets,
  ROUND(-SUM(RETAIL_DISC),2)       AS retail_discount,
  ROUND(-SUM(COUPON_DISC),2)       AS coupon_discount,
  ROUND(-SUM(COUPON_MATCH_DISC),2) AS coupon_match_discount,
  ROUND(100.0*-SUM(RETAIL_DISC)/(SUM(SALES_VALUE)-SUM(RETAIL_DISC)-SUM(COUPON_MATCH_DISC)),2)     AS retail_disc_depth_pct,
  ROUND(100.0*-SUM(COUPON_DISC)/(SUM(SALES_VALUE)-SUM(RETAIL_DISC)-SUM(COUPON_MATCH_DISC)),2)     AS coupon_disc_depth_pct,
  ROUND(100.0*-SUM(COUPON_MATCH_DISC)/(SUM(SALES_VALUE)-SUM(RETAIL_DISC)-SUM(COUPON_MATCH_DISC)),2) AS coupon_match_depth_pct,
  ROUND(100.0*SUM(CASE WHEN RETAIL_DISC<0 THEN SALES_VALUE END)/SUM(SALES_VALUE),2) AS pct_sales_with_retail_disc
FROM base;
