-- 06_promotions.sql : display / mailer analysis (DESCRIPTIVE, not causal)
-- Scope: merchandise lines in the 115 causal stores, weeks 9-101.
CREATE OR REPLACE TABLE r_promo_scope AS
SELECT promo_status, COUNT(*) lines, ROUND(SUM(SALES_VALUE),2) sales,
       ROUND(100*SUM(SALES_VALUE)/SUM(SUM(SALES_VALUE)) OVER (),2) pct_sales
FROM txn_promo WHERE is_merch=1 GROUP BY 1 ORDER BY sales DESC;

-- Product-store-week grain (weeks where the product sold at that store)
CREATE OR REPLACE TABLE psw AS
SELECT PRODUCT_ID, STORE_ID, WEEK_NO, DEPARTMENT, COMMODITY_DESC, promo_status,
       SUM(SALES_VALUE) sales, SUM(UNITS_MERCH) units,
       SUM(SALES_VALUE - RETAIL_DISC - COUPON_MATCH_DISC) gross_value  -- shelf value before retailer discounts
FROM txn_promo WHERE is_merch=1 AND in_causal_scope=1
GROUP BY ALL;

-- Matched lift: within each product-store pair, compare average weekly sales in promoted
-- weeks vs non-promoted weeks. Only pairs with both kinds of week are used.
CREATE OR REPLACE TABLE r_promo_lift AS
WITH ps AS (
  SELECT PRODUCT_ID, STORE_ID, promo_status, AVG(sales) avg_sales, AVG(units) avg_units, AVG(gross_value) avg_gross, COUNT(*) n_weeks
  FROM psw GROUP BY 1,2,3),
base AS (SELECT PRODUCT_ID, STORE_ID, avg_sales base_sales, avg_units base_units, avg_gross base_gross FROM ps WHERE promo_status='No promotion'),
pr AS (SELECT * FROM ps WHERE promo_status<>'No promotion')
SELECT pr.promo_status,
       COUNT(*)                                   AS matched_product_store_pairs,
       SUM(pr.n_weeks)                            AS promoted_weeks,
       ROUND(SUM(pr.avg_sales),2)                 AS sum_avg_promo_sales,
       ROUND(SUM(b.base_sales),2)                 AS sum_avg_base_sales,
       ROUND(100*(SUM(pr.avg_sales)/SUM(b.base_sales)-1),1)   AS sales_lift_pct,
       ROUND(100*(SUM(pr.avg_units)/SUM(b.base_units)-1),1)   AS unit_lift_pct,
       ROUND(100*(SUM(pr.avg_gross)/SUM(b.base_gross)-1),1)   AS gross_value_lift_pct,
       ROUND(100*(MEDIAN(pr.avg_sales/b.base_sales)-1),1)     AS median_pair_lift_pct
FROM pr JOIN base b USING (PRODUCT_ID, STORE_ID)
GROUP BY 1 ORDER BY sales_lift_pct DESC;

-- Same matched lift for "any promotion" by department
CREATE OR REPLACE TABLE r_promo_lift_dept AS
WITH ps AS (
  SELECT PRODUCT_ID, STORE_ID, DEPARTMENT, (promo_status<>'No promotion') AS promoted, AVG(sales) avg_sales, AVG(units) avg_units
  FROM psw GROUP BY 1,2,3,4),
j AS (SELECT p.DEPARTMENT, p.avg_sales promo, b.avg_sales base, p.avg_units promo_u, b.avg_units base_u
      FROM ps p JOIN ps b ON p.PRODUCT_ID=b.PRODUCT_ID AND p.STORE_ID=b.STORE_ID AND p.promoted AND NOT b.promoted)
SELECT DEPARTMENT, COUNT(*) matched_pairs, ROUND(100*(SUM(promo)/SUM(base)-1),1) sales_lift_pct,
       ROUND(100*(SUM(promo_u)/SUM(base_u)-1),1) unit_lift_pct
FROM j GROUP BY 1 HAVING COUNT(*) >= 500 ORDER BY unit_lift_pct DESC;

-- Discount depth by promo status (retail-funded discount as % of pre-discount value)
CREATE OR REPLACE TABLE r_promo_discount AS
SELECT promo_status,
       ROUND(100*-SUM(RETAIL_DISC)/(SUM(SALES_VALUE)-SUM(RETAIL_DISC)-SUM(COUPON_MATCH_DISC)),2) retail_disc_depth_pct,
       ROUND(100.0*SUM(CASE WHEN RETAIL_DISC<0 THEN 1 ELSE 0 END)/COUNT(*),2) pct_lines_discounted
FROM txn_promo WHERE is_merch=1 AND in_causal_scope=1 GROUP BY 1 ORDER BY 1;
