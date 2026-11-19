-- 07_campaigns.sql : coupon redemption by campaign
CREATE OR REPLACE TABLE r_campaign AS
WITH tgt AS (SELECT CAMPAIGN, COUNT(DISTINCT household_key) targeted_hh FROM clean_campaign_table GROUP BY 1),
cpn AS (SELECT CAMPAIGN, COUNT(DISTINCT COUPON_UPC) coupons_offered FROM clean_coupon GROUP BY 1),
red AS (SELECT CAMPAIGN, COUNT(*) redemptions, COUNT(DISTINCT household_key) redeeming_hh,
               COUNT(DISTINCT COUPON_UPC) coupons_redeemed FROM clean_coupon_redempt GROUP BY 1)
SELECT d.CAMPAIGN, d.DESCRIPTION AS campaign_type, d.START_DAY, d.END_DAY, d.END_DAY-d.START_DAY+1 AS duration_days,
       d.ends_after_data, t.targeted_hh, c.coupons_offered,
       COALESCE(r.redemptions,0) redemptions, COALESCE(r.redeeming_hh,0) redeeming_hh,
       ROUND(100.0*COALESCE(r.redeeming_hh,0)/t.targeted_hh,2) AS hh_redemption_rate_pct,
       ROUND(1.0*COALESCE(r.redemptions,0)/t.targeted_hh,3)  AS redemptions_per_targeted_hh
FROM clean_campaign_desc d JOIN tgt t USING (CAMPAIGN) JOIN cpn c USING (CAMPAIGN) LEFT JOIN red r USING (CAMPAIGN)
ORDER BY hh_redemption_rate_pct DESC;

CREATE OR REPLACE TABLE r_campaign_type AS
SELECT campaign_type, COUNT(*) campaigns, SUM(targeted_hh) targeted_hh_slots, SUM(redemptions) redemptions,
       SUM(redeeming_hh) redeeming_hh_slots,
       ROUND(100.0*SUM(redeeming_hh)/SUM(targeted_hh),2) hh_redemption_rate_pct,
       ROUND(AVG(duration_days),1) avg_duration_days
FROM r_campaign GROUP BY 1 ORDER BY 1;

-- Distinct totals (counting a household/day/coupon once even if credited to 2 campaigns)
CREATE OR REPLACE TABLE r_coupon_totals AS
SELECT (SELECT COUNT(*) FROM clean_coupon_redempt) redemption_rows,
       (SELECT COUNT(*) FROM (SELECT DISTINCT household_key, DAY, COUPON_UPC FROM clean_coupon_redempt)) distinct_redemptions,
       (SELECT COUNT(DISTINCT household_key) FROM clean_coupon_redempt) redeeming_households,
       (SELECT COUNT(DISTINCT household_key) FROM clean_campaign_table) targeted_households,
       (SELECT COUNT(*) FROM clean_transactions WHERE COUPON_DISC<0) txn_lines_with_coupon_disc;

-- Descriptive: average weekly spend of targeted households in campaign weeks, redeemers vs non-redeemers
-- (self-selection: redeemers are likely heavier shoppers already - NOT a causal effect)
CREATE OR REPLACE TABLE r_campaign_redeemer_spend AS
WITH tgt AS (SELECT ct.CAMPAIGN, ct.household_key,
                    CASE WHEN EXISTS (SELECT 1 FROM clean_coupon_redempt r WHERE r.CAMPAIGN=ct.CAMPAIGN AND r.household_key=ct.household_key)
                         THEN 'Redeemed' ELSE 'Did not redeem' END grp
             FROM clean_campaign_table ct),
sp AS (SELECT tg.CAMPAIGN, tg.grp, tg.household_key,
              SUM(CASE WHEN t.DAY BETWEEN d.START_DAY AND LEAST(d.END_DAY,711) THEN t.SALES_VALUE ELSE 0 END)
                / ((LEAST(d.END_DAY,711)-d.START_DAY+1)/7.0) AS wk_spend_in,
              SUM(CASE WHEN t.DAY BETWEEN d.START_DAY-56 AND d.START_DAY-1 THEN t.SALES_VALUE ELSE 0 END)/8.0 AS wk_spend_pre
       FROM tgt tg JOIN clean_campaign_desc d USING (CAMPAIGN)
       LEFT JOIN clean_transactions t ON t.household_key=tg.household_key
       WHERE d.START_DAY > 56
       GROUP BY 1,2,3, d.START_DAY, d.END_DAY)
SELECT grp, COUNT(*) hh_campaign_pairs, ROUND(AVG(wk_spend_pre),2) avg_weekly_spend_8wk_before,
       ROUND(AVG(wk_spend_in),2) avg_weekly_spend_during,
       ROUND(100*(AVG(wk_spend_in)/AVG(wk_spend_pre)-1),1) change_pct
FROM sp GROUP BY 1;
