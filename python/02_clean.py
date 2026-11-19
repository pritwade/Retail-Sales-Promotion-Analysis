"""Step 2 - Clean with documented rules and reconcile.
Usage: python3 02_clean.py <db_path> <out_dir>
Reads raw_* tables created in Step 1, writes clean_* tables, a cleaning log,
a reconciliation table, and CSV/Parquet exports."""
import sys, os, duckdb

db, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
con = duckdb.connect(db)
con.execute("SET memory_limit='3GB'")
one = lambda s: con.execute(s).fetchone()[0]
log = []  # (rule_id, table, action, rule, rows_affected, sales_affected, units_affected, reason)

NON_MERCH = "('KIOSK-GAS','MISC SALES TRAN','MISC. TRANS.','COUP/STR & MFG')"
NOISE = 0.005  # discounts smaller than half a cent are floating-point residue

# ---------- PRODUCT ----------
con.execute(f"""
CREATE OR REPLACE TABLE clean_product AS
SELECT PRODUCT_ID, MANUFACTURER,
       COALESCE(NULLIF(TRIM(DEPARTMENT),''),'UNKNOWN')            AS DEPARTMENT,
       BRAND,
       CASE WHEN TRIM(COMMODITY_DESC)='' OR COMMODITY_DESC='NO COMMODITY DESCRIPTION'
            THEN 'UNKNOWN' ELSE TRIM(COMMODITY_DESC) END            AS COMMODITY_DESC,
       CASE WHEN TRIM(SUB_COMMODITY_DESC)='' OR SUB_COMMODITY_DESC='NO SUBCOMMODITY DESCRIPTION'
            THEN 'UNKNOWN' ELSE TRIM(SUB_COMMODITY_DESC) END        AS SUB_COMMODITY_DESC,
       COALESCE(NULLIF(TRIM(CURR_SIZE_OF_PRODUCT),''),'UNKNOWN')  AS CURR_SIZE_OF_PRODUCT,
       CASE WHEN TRIM(DEPARTMENT) IN {NON_MERCH} OR TRIM(DEPARTMENT)='' THEN 0 ELSE 1 END AS is_merch
FROM raw_product""")
log += [
 ("P1","product","relabel","Blank DEPARTMENT -> 'UNKNOWN'", one("SELECT COUNT(*) FROM raw_product WHERE TRIM(DEPARTMENT)=''"), None, None,
  "Keeps products joinable; all their transaction rows are 0 qty/0 sales and are removed by T1"),
 ("P2","product","relabel","Blank or 'NO COMMODITY/SUBCOMMODITY DESCRIPTION' -> 'UNKNOWN'",
  one("SELECT COUNT(*) FROM raw_product WHERE TRIM(COMMODITY_DESC)='' OR COMMODITY_DESC='NO COMMODITY DESCRIPTION' OR TRIM(SUB_COMMODITY_DESC)='' OR SUB_COMMODITY_DESC='NO SUBCOMMODITY DESCRIPTION'"), None, None,
  "One consistent label for missing category text"),
 ("P3","product","relabel","Blank CURR_SIZE_OF_PRODUCT -> 'UNKNOWN'", one("SELECT COUNT(*) FROM raw_product WHERE TRIM(CURR_SIZE_OF_PRODUCT)=''"), None, None,
  "Size is descriptive only; not used in KPIs"),
 ("P4","product","flag",f"is_merch = 0 for departments {NON_MERCH} and blank (UNKNOWN) department", one(f"SELECT COUNT(*) FROM raw_product WHERE TRIM(DEPARTMENT) IN {NON_MERCH} OR TRIM(DEPARTMENT)=''"), None, None,
  "Fuel/misc/store-coupon lines are not grocery merchandise; their QUANTITY is not an item count"),
]

# ---------- TRANSACTIONS ----------
before = con.execute("SELECT COUNT(*), ROUND(SUM(SALES_VALUE),2), SUM(QUANTITY), ROUND(SUM(RETAIL_DISC),2), ROUND(SUM(COUPON_DISC),2), ROUND(SUM(COUPON_MATCH_DISC),2), COUNT(DISTINCT BASKET_ID), COUNT(DISTINCT household_key) FROM raw_transaction_data").fetchone()

EMPTY = f"(QUANTITY=0 AND SALES_VALUE=0 AND ABS(RETAIL_DISC)<{NOISE} AND ABS(COUPON_DISC)<{NOISE} AND ABS(COUPON_MATCH_DISC)<{NOISE})"
t1 = con.execute(f"SELECT COUNT(*), ROUND(SUM(SALES_VALUE),2), SUM(QUANTITY) FROM raw_transaction_data WHERE {EMPTY}").fetchone()
noise_rows = one(f"""SELECT COUNT(*) FROM raw_transaction_data WHERE NOT {EMPTY} AND
   ((ABS(RETAIL_DISC)>0 AND ABS(RETAIL_DISC)<{NOISE}) OR (ABS(COUPON_DISC)>0 AND ABS(COUPON_DISC)<{NOISE}) OR (ABS(COUPON_MATCH_DISC)>0 AND ABS(COUPON_MATCH_DISC)<{NOISE}))""")

con.execute(f"""
CREATE OR REPLACE TABLE clean_transactions AS
SELECT t.household_key, t.BASKET_ID, t.DAY, t.WEEK_NO, t.STORE_ID, t.PRODUCT_ID,
       CAST(t.TRANS_TIME AS INTEGER)                                         AS TRANS_TIME,
       CAST(SUBSTR(t.TRANS_TIME,1,2) AS INTEGER)                             AS TRANS_HOUR,
       t.QUANTITY,
       ROUND(t.SALES_VALUE,2)                                                AS SALES_VALUE,
       CASE WHEN ABS(t.RETAIL_DISC)       < {NOISE} THEN 0 ELSE ROUND(t.RETAIL_DISC,2)       END AS RETAIL_DISC,
       CASE WHEN ABS(t.COUPON_DISC)       < {NOISE} THEN 0 ELSE ROUND(t.COUPON_DISC,2)       END AS COUPON_DISC,
       CASE WHEN ABS(t.COUPON_MATCH_DISC) < {NOISE} THEN 0 ELSE ROUND(t.COUPON_MATCH_DISC,2) END AS COUPON_MATCH_DISC,
       p.is_merch,
       CASE WHEN p.is_merch=1 THEN t.QUANTITY ELSE 0 END                     AS UNITS_MERCH,
       CASE WHEN t.QUANTITY>0 AND t.SALES_VALUE=0 THEN 1 ELSE 0 END          AS is_free_item,
       CASE WHEN t.QUANTITY=0 AND t.SALES_VALUE>0 THEN 1 ELSE 0 END          AS is_zero_qty_sale,
       CASE WHEN t.QUANTITY=0 AND t.SALES_VALUE=0 THEN 1 ELSE 0 END          AS is_discount_only_line,
       CASE WHEN t.RETAIL_DISC >= {NOISE} THEN 1 ELSE 0 END                  AS is_pos_retail_disc,
       CASE WHEN t.WEEK_NO BETWEEN 2 AND 101 THEN 1 ELSE 0 END               AS is_full_week,
       CASE WHEN t.WEEK_NO BETWEEN 9 AND 101 THEN 1 ELSE 0 END               AS in_causal_weeks,
       CASE WHEN d.household_key IS NOT NULL THEN 1 ELSE 0 END               AS has_demographics
FROM raw_transaction_data t
JOIN clean_product p USING (PRODUCT_ID)
LEFT JOIN raw_hh_demographic d USING (household_key)
WHERE NOT {EMPTY.replace('QUANTITY','t.QUANTITY').replace('SALES_VALUE','t.SALES_VALUE').replace('(RETAIL','(t.RETAIL').replace('(COUPON','(t.COUPON')}""")

flags = lambda col: con.execute(f"SELECT COUNT(*), ROUND(SUM(SALES_VALUE),2), SUM(QUANTITY) FROM clean_transactions WHERE {col}").fetchone()
f_nm, f_free, f_zq, f_pos, f_part = flags("is_merch=0"), flags("is_free_item=1"), flags("is_zero_qty_sale=1"), flags("is_pos_retail_disc=1"), flags("is_full_week=0")
f_nodemo = flags("has_demographics=0")
f_do = con.execute("SELECT COUNT(*), ROUND(SUM(COUPON_DISC),2), ROUND(SUM(RETAIL_DISC),2) FROM clean_transactions WHERE is_discount_only_line=1").fetchone()
log += [
 ("T1","transactions","remove","QUANTITY = 0 AND SALES_VALUE = 0 AND all three discounts = 0", t1[0], t1[1], t1[2],
  "No sale, no unit, no discount: carries no information"),
 ("T1b","transactions","flag",f"is_discount_only_line: QUANTITY = 0 AND SALES_VALUE = 0 but a discount exists (coupon {f_do[1]}, retail {f_do[2]})", f_do[0], 0, 0,
  "Kept: coupon/discount lines with no product sale; removing them would understate coupon discounts"),
 ("T2","transactions","flag","is_merch = 0 (non-merchandise departments); UNITS_MERCH = 0 for these rows", f_nm[0], f_nm[1], f_nm[2],
  "Kept in total sales (real revenue) but excluded from units and merchandising analysis"),
 ("T3","transactions","flag","is_free_item: QUANTITY > 0 AND SALES_VALUE = 0", f_free[0], f_free[1], f_free[2],
  "Likely free/fully discounted items; kept, counted in units, no sales"),
 ("T4","transactions","flag","is_zero_qty_sale: QUANTITY = 0 AND SALES_VALUE > 0", f_zq[0], f_zq[1], f_zq[2],
  "Kept: sales are real money; quantity cannot be verified"),
 ("T5","transactions","set to 0",f"Discount values with |x| < {NOISE} set to 0", noise_rows, 0, 0,
  "Floating-point residue (e.g. 2.2e-16), not real discounts"),
 ("T6","transactions","flag","is_pos_retail_disc: RETAIL_DISC >= 0.005 (wrong sign)", f_pos[0], f_pos[1], f_pos[2],
  "Kept as-is; too small to matter, documented"),
 ("T7","transactions","flag","is_full_week = 0 for partial weeks 1 (5 days) and 102 (6 days)", f_part[0], f_part[1], f_part[2],
  "Kept in totals; excluded from week-over-week and forecast"),
 ("T8","transactions","flag","has_demographics = 0 (household not in hh_demographic)", f_nodemo[0], f_nodemo[1], f_nodemo[2],
  "Kept; demographic charts will state they cover only households with demographics"),
 ("T9","transactions","type","TRANS_TIME text 'HHMM' -> integer; TRANS_HOUR derived; money rounded to 2 dp", None, None, None,
  "Consistent types for SQL/Power BI"),
]

# ---------- DEMOGRAPHICS ----------
con.execute("""
CREATE OR REPLACE TABLE clean_hh_demographic AS
SELECT *, CASE WHEN HH_COMP_DESC LIKE 'Single%' AND HOUSEHOLD_SIZE_DESC <> '1' THEN 1 ELSE 0 END AS is_inconsistent_comp
FROM raw_hh_demographic""")
log.append(("D1","hh_demographic","flag","is_inconsistent_comp: 'Single' household with size >= 2",
            one("SELECT SUM(is_inconsistent_comp) FROM clean_hh_demographic"), None, None,
            "Kept; contradiction is documented, not corrected (we cannot know which field is right)"))

# ---------- CAMPAIGNS / COUPONS ----------
con.execute("CREATE OR REPLACE TABLE clean_campaign_desc AS SELECT *, CASE WHEN END_DAY > 711 THEN 1 ELSE 0 END AS ends_after_data FROM raw_campaign_desc")
con.execute("CREATE OR REPLACE TABLE clean_campaign_table AS SELECT * FROM raw_campaign_table")
cp_before = one("SELECT COUNT(*) FROM raw_coupon")
con.execute("CREATE OR REPLACE TABLE clean_coupon AS SELECT DISTINCT * FROM raw_coupon")
con.execute("""
CREATE OR REPLACE TABLE clean_coupon_redempt AS
SELECT r.*, CASE WHEN m.n_campaigns > 1 THEN 1 ELSE 0 END AS is_multi_campaign_redemption
FROM raw_coupon_redempt r
JOIN (SELECT household_key, DAY, COUPON_UPC, COUNT(DISTINCT CAMPAIGN) n_campaigns
      FROM raw_coupon_redempt GROUP BY 1,2,3) m USING (household_key, DAY, COUPON_UPC)""")
log += [
 ("C1","coupon","remove","Exact duplicate rows", cp_before - one("SELECT COUNT(*) FROM clean_coupon"), None, None,
  "Same coupon-product-campaign listed more than once"),
 ("C2","coupon_redempt","flag","is_multi_campaign_redemption: same hh/day/UPC under >1 campaign",
  one("SELECT SUM(is_multi_campaign_redemption) FROM clean_coupon_redempt"), None, None,
  "Kept so each campaign gets its row; totals across campaigns will count distinct hh/day/UPC"),
 ("C3","campaign_desc","flag","ends_after_data: END_DAY > 711", one("SELECT SUM(ends_after_data) FROM clean_campaign_desc"), None, None,
  "Campaign 24 window is cut off by the end of the data"),
]

# ---------- CAUSAL ----------
c_before = one("SELECT COUNT(*) FROM raw_causal_data")
con.execute("""
CREATE OR REPLACE TABLE clean_causal AS
SELECT PRODUCT_ID, STORE_ID, WEEK_NO,
       MAX(CASE WHEN display <> '0' THEN 1 ELSE 0 END) AS on_display,
       MAX(CASE WHEN mailer  <> '0' THEN 1 ELSE 0 END) AS on_mailer,
       STRING_AGG(DISTINCT display, '|' ORDER BY display) AS display_codes,
       STRING_AGG(DISTINCT mailer,  '|' ORDER BY mailer)  AS mailer_codes,
       COUNT(*) AS source_rows
FROM raw_causal_data GROUP BY 1,2,3""")
c_after = one("SELECT COUNT(*) FROM clean_causal")
log.append(("K1","causal","collapse","One row per PRODUCT_ID+STORE_ID+WEEK_NO; on_display/on_mailer = 1 if ANY source row is flagged",
            c_before - c_after, None, None,
            "15,245 keys had 2 rows with conflicting flags; collapsing prevents join fan-out (double counting sales)"))

# ---------- RECONCILIATION ----------
after = con.execute("SELECT COUNT(*), ROUND(SUM(SALES_VALUE),2), SUM(QUANTITY), ROUND(SUM(RETAIL_DISC),2), ROUND(SUM(COUPON_DISC),2), ROUND(SUM(COUPON_MATCH_DISC),2), COUNT(DISTINCT BASKET_ID), COUNT(DISTINCT household_key) FROM clean_transactions").fetchone()
merch_units = one("SELECT SUM(UNITS_MERCH) FROM clean_transactions")
merch_sales = one("SELECT ROUND(SUM(SALES_VALUE),2) FROM clean_transactions WHERE is_merch=1")
names = ["rows","sales","units (raw QUANTITY)","retail_disc","coupon_disc","coupon_match_disc","baskets","households"]
recon = [(n, b, a, None if b is None else round(a - b, 2)) for n, b, a in zip(names, before, after)]
recon += [("merch units (UNITS_MERCH)", None, merch_units, None), ("merch sales (is_merch=1)", None, merch_sales, None)]
con.execute("CREATE OR REPLACE TABLE reconciliation (metric VARCHAR, before_clean DOUBLE, after_clean DOUBLE, diff DOUBLE)")
con.executemany("INSERT INTO reconciliation VALUES (?,?,?,?)", recon)
con.execute("CREATE OR REPLACE TABLE cleaning_log (rule_id VARCHAR, tbl VARCHAR, action VARCHAR, rule VARCHAR, rows_affected BIGINT, sales_affected DOUBLE, units_affected DOUBLE, reason VARCHAR)")
con.executemany("INSERT INTO cleaning_log VALUES (?,?,?,?,?,?,?,?)", log)

# Check: removed rows explain the full difference
assert after[0] == before[0] - t1[0], "row count does not reconcile"
assert abs(after[1] - before[1]) < 0.01, "sales do not reconcile"
assert after[2] == before[2] - t1[2], "units do not reconcile"

# ---------- EXPORT ----------
for t in ["clean_transactions","clean_product","clean_hh_demographic","clean_campaign_desc","clean_campaign_table",
          "clean_coupon","clean_coupon_redempt","clean_causal","cleaning_log","reconciliation"]:
    con.execute(f"COPY {t} TO '{out}/{t}.parquet' (FORMAT PARQUET)")
    if t != "clean_causal":  # causal stays Parquet only (large)
        con.execute(f"COPY {t} TO '{out}/{t}.csv' (HEADER)")

print(con.execute("SELECT rule_id, action, rule, rows_affected, sales_affected, units_affected FROM cleaning_log").fetchdf().to_string())
print()
print(con.execute("SELECT * FROM reconciliation").fetchdf().to_string())
print("\nclean_causal rows:", f"{c_after:,}", "| on_display:", one("SELECT SUM(on_display) FROM clean_causal"), "| on_mailer:", one("SELECT SUM(on_mailer) FROM clean_causal"))
con.close()
