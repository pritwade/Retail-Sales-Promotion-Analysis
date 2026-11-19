-- 00_txn_promo.sql
-- Join transactions + product + causal (deduplicated in Step 2) into one analysis table.
-- Promo flags exist only for the 115 causal stores and weeks 9-101 (in_causal_scope = 1).
-- Outside that scope promo status is UNKNOWN, not "not promoted".
CREATE OR REPLACE TABLE txn_promo AS
WITH causal_stores AS (SELECT DISTINCT STORE_ID FROM clean_causal)
SELECT t.*,
       p.DEPARTMENT, p.COMMODITY_DESC, p.SUB_COMMODITY_DESC, p.BRAND,
       CASE WHEN cs.STORE_ID IS NOT NULL AND t.WEEK_NO BETWEEN 9 AND 101 THEN 1 ELSE 0 END AS in_causal_scope,
       COALESCE(c.on_display, 0) AS on_display,
       COALESCE(c.on_mailer, 0)  AS on_mailer,
       CASE WHEN cs.STORE_ID IS NULL OR t.WEEK_NO NOT BETWEEN 9 AND 101 THEN 'Unknown (no causal data)'
            WHEN c.on_display = 1 AND c.on_mailer = 1 THEN 'Display + Mailer'
            WHEN c.on_display = 1 THEN 'Display only'
            WHEN c.on_mailer = 1 THEN 'Mailer only'
            ELSE 'No promotion' END AS promo_status
FROM clean_transactions t
JOIN clean_product p USING (PRODUCT_ID)
LEFT JOIN causal_stores cs USING (STORE_ID)
LEFT JOIN clean_causal c USING (PRODUCT_ID, STORE_ID, WEEK_NO);
