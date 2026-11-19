-- 08_rfm.sql : RFM household segmentation (all 2,500 households)
-- Recency = 711 - last purchase DAY; Frequency = distinct baskets; Monetary = total sales.
-- Scores 1-5 with NTILE (5 = best). Recency scored so that more recent = higher.
CREATE OR REPLACE TABLE r_rfm_household AS
WITH r AS (
  SELECT household_key, 711 - MAX(DAY) recency_days, COUNT(DISTINCT BASKET_ID) frequency,
         ROUND(SUM(SALES_VALUE),2) monetary, MIN(WEEK_NO) first_week
  FROM clean_transactions GROUP BY 1),
s AS (
  SELECT *, NTILE(5) OVER (ORDER BY recency_days DESC) r_score,
            NTILE(5) OVER (ORDER BY frequency ASC)     f_score,
            NTILE(5) OVER (ORDER BY monetary ASC)      m_score
  FROM r)
SELECT *, CAST(r_score AS VARCHAR)||CAST(f_score AS VARCHAR)||CAST(m_score AS VARCHAR) rfm_code,
  CASE WHEN r_score>=4 AND f_score>=4 AND m_score>=4 THEN '1 Champions'
       WHEN r_score>=3 AND f_score>=3 AND m_score>=3 THEN '2 Loyal'
       WHEN r_score<=2 AND (f_score>=3 OR m_score>=3) THEN '4 At Risk'
       WHEN r_score<=2 THEN '6 Lapsed / Low'
       WHEN f_score<=2 AND m_score<=2 THEN '5 Occasional'
       ELSE '3 Potential' END AS segment
FROM s;

CREATE OR REPLACE TABLE r_rfm_segment AS
SELECT segment, COUNT(*) households,
       ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),2) pct_households,
       ROUND(SUM(monetary),2) sales, ROUND(100*SUM(monetary)/SUM(SUM(monetary)) OVER (),2) pct_sales,
       ROUND(AVG(monetary),2) avg_sales_per_hh, ROUND(AVG(frequency),1) avg_baskets,
       ROUND(SUM(monetary)/SUM(frequency),2) avg_basket_value, ROUND(AVG(recency_days),1) avg_recency_days,
       ROUND(MEDIAN(recency_days),1) median_recency_days
FROM r_rfm_household GROUP BY 1 ORDER BY 1;

-- Demographic profile per segment (only households with demographics; coverage shown)
CREATE OR REPLACE TABLE r_rfm_demo AS
WITH j AS (SELECT r.segment, d.* FROM r_rfm_household r LEFT JOIN clean_hh_demographic d USING (household_key)),
cov AS (SELECT segment, COUNT(*) hh, COUNT(AGE_DESC) hh_with_demo FROM j GROUP BY 1),
top_inc AS (SELECT segment, INCOME_DESC, COUNT(*) n, ROW_NUMBER() OVER (PARTITION BY segment ORDER BY COUNT(*) DESC) rn FROM j WHERE INCOME_DESC IS NOT NULL GROUP BY 1,2),
top_age AS (SELECT segment, AGE_DESC, COUNT(*) n, ROW_NUMBER() OVER (PARTITION BY segment ORDER BY COUNT(*) DESC) rn FROM j WHERE AGE_DESC IS NOT NULL GROUP BY 1,2),
kids AS (SELECT segment, ROUND(100.0*SUM(CASE WHEN KID_CATEGORY_DESC<>'None/Unknown' THEN 1 ELSE 0 END)/COUNT(*),1) pct_with_kids FROM j WHERE AGE_DESC IS NOT NULL GROUP BY 1)
SELECT cov.segment, cov.hh, cov.hh_with_demo, ROUND(100.0*cov.hh_with_demo/cov.hh,1) pct_with_demo,
       a.AGE_DESC most_common_age, i.INCOME_DESC most_common_income, k.pct_with_kids
FROM cov LEFT JOIN top_age a ON a.segment=cov.segment AND a.rn=1
LEFT JOIN top_inc i ON i.segment=cov.segment AND i.rn=1
LEFT JOIN kids k ON k.segment=cov.segment ORDER BY 1;

-- Segment x department mix (merchandise)
CREATE OR REPLACE TABLE r_rfm_dept AS
SELECT r.segment, t.DEPARTMENT, ROUND(SUM(t.SALES_VALUE),2) sales,
       ROUND(100*SUM(t.SALES_VALUE)/SUM(SUM(t.SALES_VALUE)) OVER (PARTITION BY r.segment),2) pct_of_segment
FROM txn_promo t JOIN r_rfm_household r USING (household_key)
WHERE t.is_merch=1 AND t.DEPARTMENT IN ('GROCERY','DRUG GM','PRODUCE','MEAT','MEAT-PCKGD','DELI')
GROUP BY 1,2 ORDER BY 1,3 DESC;
