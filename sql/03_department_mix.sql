-- 03_department_mix.sql : sales, units, mix and private-label share by department (merchandise only for mix)
CREATE OR REPLACE TABLE r_department AS
WITH d AS (
  SELECT DEPARTMENT, MAX(is_merch) is_merch,
         SUM(SALES_VALUE) sales, SUM(UNITS_MERCH) units,
         COUNT(DISTINCT BASKET_ID) baskets, COUNT(DISTINCT household_key) households,
         SUM(CASE WHEN BRAND='Private' THEN SALES_VALUE ELSE 0 END) private_sales,
         SUM(CASE WHEN WEEK_NO BETWEEN 24 AND 49 THEN SALES_VALUE ELSE 0 END) sales_y1w,
         SUM(CASE WHEN WEEK_NO BETWEEN 76 AND 101 THEN SALES_VALUE ELSE 0 END) sales_y2w,
         -SUM(RETAIL_DISC) retail_disc, -SUM(COUPON_DISC) coupon_disc, -SUM(COUPON_MATCH_DISC) match_disc,
         SUM(SALES_VALUE) - SUM(RETAIL_DISC) - SUM(COUPON_MATCH_DISC) gross_value
  FROM txn_promo GROUP BY 1)
SELECT DEPARTMENT, is_merch,
       ROUND(sales,2) sales, units, baskets, households,
       ROUND(100*sales/SUM(sales) OVER (),2)                                                   AS pct_total_sales,
       ROUND(CASE WHEN is_merch=1 THEN 100*sales/SUM(CASE WHEN is_merch=1 THEN sales END) OVER () END,2) AS pct_merch_sales,
       ROUND(100.0*baskets/(SELECT COUNT(DISTINCT BASKET_ID) FROM clean_transactions),2)        AS basket_penetration_pct,
       ROUND(CASE WHEN units>0 THEN sales/units END,2)                                          AS avg_price_per_unit,
       ROUND(100*private_sales/NULLIF(sales,0),2)                                               AS private_label_pct,
       ROUND(100*(sales_y2w-sales_y1w)/NULLIF(sales_y1w,0),2)                                   AS growth_y2_vs_y1_pct,
       ROUND(100*retail_disc/NULLIF(gross_value,0),2)                                           AS retail_disc_depth_pct,
       ROUND(100*coupon_disc/NULLIF(gross_value,0),2)                                           AS coupon_disc_depth_pct,
       RANK() OVER (ORDER BY sales DESC)                                                        AS sales_rank
FROM d ORDER BY sales DESC;

CREATE OR REPLACE TABLE r_brand AS
SELECT BRAND, ROUND(SUM(SALES_VALUE),2) sales, SUM(UNITS_MERCH) units,
       ROUND(100*SUM(SALES_VALUE)/SUM(SUM(SALES_VALUE)) OVER (),2) pct_merch_sales,
       ROUND(SUM(SALES_VALUE)/SUM(UNITS_MERCH),2) avg_price_per_unit,
       COUNT(DISTINCT PRODUCT_ID) products_sold
FROM txn_promo WHERE is_merch=1 GROUP BY 1;
