-- 04_commodity_rank.sql : commodity performance, rank within department (window), top/bottom performers
CREATE OR REPLACE TABLE r_commodity AS
WITH c AS (
  SELECT DEPARTMENT, COMMODITY_DESC,
         SUM(SALES_VALUE) sales, SUM(UNITS_MERCH) units, COUNT(DISTINCT BASKET_ID) baskets,
         COUNT(DISTINCT household_key) households,
         SUM(CASE WHEN BRAND='Private' THEN SALES_VALUE ELSE 0 END) private_sales,
         SUM(CASE WHEN WEEK_NO BETWEEN 24 AND 49 THEN SALES_VALUE ELSE 0 END) sales_y1w,
         SUM(CASE WHEN WEEK_NO BETWEEN 76 AND 101 THEN SALES_VALUE ELSE 0 END) sales_y2w
  FROM txn_promo WHERE is_merch=1 AND COMMODITY_DESC <> 'UNKNOWN' GROUP BY 1,2)
SELECT DEPARTMENT, COMMODITY_DESC, ROUND(sales,2) sales, units, baskets, households,
       ROUND(100*sales/SUM(sales) OVER (),3)                         AS pct_merch_sales,
       ROUND(100*sales/SUM(sales) OVER (PARTITION BY DEPARTMENT),2)  AS pct_of_department,
       RANK() OVER (PARTITION BY DEPARTMENT ORDER BY sales DESC)     AS rank_in_department,
       RANK() OVER (ORDER BY sales DESC)                             AS overall_rank,
       ROUND(100*private_sales/NULLIF(sales,0),2)                    AS private_label_pct,
       ROUND(sales_y1w,2) sales_wk24_49, ROUND(sales_y2w,2) sales_wk76_101,
       ROUND(sales_y2w - sales_y1w,2)                                AS growth_abs,
       ROUND(100*(sales_y2w-sales_y1w)/NULLIF(sales_y1w,0),2)        AS growth_pct
FROM c ORDER BY sales DESC;

CREATE OR REPLACE TABLE r_commodity_top10 AS SELECT * FROM r_commodity ORDER BY sales DESC LIMIT 10;
-- Bottom performers: among commodities large enough to matter (>= $10,000 in weeks 24-49),
-- the 10 with the largest sales decline between the two matched 26-week windows.
CREATE OR REPLACE TABLE r_commodity_decliners AS
SELECT * FROM r_commodity WHERE sales_wk24_49 >= 10000 ORDER BY growth_pct ASC LIMIT 10;
CREATE OR REPLACE TABLE r_commodity_growers AS
SELECT * FROM r_commodity WHERE sales_wk24_49 >= 10000 ORDER BY growth_pct DESC LIMIT 10;
CREATE OR REPLACE TABLE r_commodity_bottom10_sales AS
SELECT * FROM r_commodity ORDER BY sales ASC LIMIT 10;
