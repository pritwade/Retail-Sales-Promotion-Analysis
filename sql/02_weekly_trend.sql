-- 02_weekly_trend.sql : weekly sales with week-over-week change (LAG), running total, 4-week moving average
CREATE OR REPLACE TABLE r_weekly AS
WITH wk AS (
  SELECT WEEK_NO, MAX(is_full_week) AS is_full_week,
         ROUND(SUM(SALES_VALUE),2) AS sales,
         ROUND(SUM(CASE WHEN is_merch=1 THEN SALES_VALUE END),2) AS merch_sales,
         SUM(UNITS_MERCH) AS merch_units,
         COUNT(DISTINCT BASKET_ID) AS baskets,
         COUNT(DISTINCT household_key) AS active_households
  FROM clean_transactions GROUP BY WEEK_NO)
SELECT *,
       ROUND(sales / baskets, 2)                                              AS basket_value,
       LAG(sales) OVER (ORDER BY WEEK_NO)                                     AS prev_week_sales,
       ROUND(100.0*(sales - LAG(sales) OVER (ORDER BY WEEK_NO)) / LAG(sales) OVER (ORDER BY WEEK_NO), 2) AS wow_change_pct,
       ROUND(SUM(sales) OVER (ORDER BY WEEK_NO ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 2)   AS running_total_sales,
       ROUND(AVG(sales) OVER (ORDER BY WEEK_NO ROWS BETWEEN 3 PRECEDING AND CURRENT ROW), 2)           AS ma4_sales
FROM wk ORDER BY WEEK_NO;

-- Department x week (feeds the Excel pivot and the Power BI check)
CREATE OR REPLACE TABLE r_dept_week AS
SELECT p.DEPARTMENT, t.WEEK_NO, MAX(p.is_merch) AS is_merch,
       ROUND(SUM(t.SALES_VALUE),2) AS sales, SUM(t.UNITS_MERCH) AS merch_units, COUNT(DISTINCT t.BASKET_ID) AS baskets
FROM clean_transactions t JOIN clean_product p USING (PRODUCT_ID)
GROUP BY 1,2 ORDER BY 1,2;

-- Ramp-up check: households and sales per household-week, by period
CREATE OR REPLACE TABLE r_period_summary AS
SELECT CASE WHEN WEEK_NO <= 16 THEN 'a) Weeks 1-16 (ramp-up)'
            WHEN WEEK_NO BETWEEN 24 AND 49 THEN 'b) Weeks 24-49 (year 1 window)'
            WHEN WEEK_NO BETWEEN 76 AND 101 THEN 'c) Weeks 76-101 (year 2 window)'
            ELSE 'z) other' END AS period,
       COUNT(*) AS weeks, ROUND(SUM(sales),2) AS sales, ROUND(AVG(sales),2) AS avg_weekly_sales,
       ROUND(AVG(active_households),1) AS avg_weekly_active_hh
FROM r_weekly GROUP BY 1 ORDER BY 1;
