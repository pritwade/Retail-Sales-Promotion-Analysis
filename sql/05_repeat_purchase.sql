-- 05_repeat_purchase.sql
-- (a) Commodity repeat purchase rate = households that bought the commodity in >= 2 different weeks
--     / households that bought it at least once.
CREATE OR REPLACE TABLE r_commodity_repeat AS
WITH hc AS (SELECT COMMODITY_DESC, DEPARTMENT, household_key, COUNT(DISTINCT WEEK_NO) n_weeks
            FROM txn_promo WHERE is_merch=1 AND COMMODITY_DESC<>'UNKNOWN' AND SALES_VALUE>0 GROUP BY 1,2,3)
SELECT DEPARTMENT, COMMODITY_DESC, COUNT(*) buyers,
       SUM(CASE WHEN n_weeks>=2 THEN 1 ELSE 0 END) repeat_buyers,
       ROUND(100.0*SUM(CASE WHEN n_weeks>=2 THEN 1 ELSE 0 END)/COUNT(*),2) repeat_rate_pct
FROM hc GROUP BY 1,2 ORDER BY buyers DESC;

-- (b) Household 4-week retention: of households active in period p, % also active in period p+1.
--     Periods = 4-week blocks of full weeks 2-101 (25 periods).
CREATE OR REPLACE TABLE r_hh_retention AS
WITH hp AS (SELECT DISTINCT household_key, (WEEK_NO-2)//4 + 1 AS period
            FROM clean_transactions WHERE is_full_week=1),
nxt AS (SELECT household_key, period,
               LEAD(period) OVER (PARTITION BY household_key ORDER BY period) AS next_period FROM hp)
SELECT period, MIN(period)*4-2 AS first_week, COUNT(*) active_hh,
       SUM(CASE WHEN next_period = period+1 THEN 1 ELSE 0 END) retained_next_period,
       ROUND(100.0*SUM(CASE WHEN next_period = period+1 THEN 1 ELSE 0 END)/COUNT(*),2) retention_pct
FROM nxt WHERE period < 25 GROUP BY period ORDER BY period;
