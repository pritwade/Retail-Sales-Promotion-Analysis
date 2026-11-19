"""Step 1 - Load and profile all raw files.
Usage: python3 01_profile.py <raw_dir> <db_path>
Loads every CSV into DuckDB (raw_* tables, types auto-detected), then prints
row counts, schema, nulls, duplicates and data-quality checks."""
import sys, duckdb

raw, db = sys.argv[1], sys.argv[2]
con = duckdb.connect(db)
files = ["transaction_data", "product", "hh_demographic", "campaign_desc",
         "campaign_table", "coupon", "coupon_redempt"]
for f in files:
    con.execute(f"CREATE OR REPLACE TABLE raw_{f} AS "
                f"SELECT * FROM read_csv_auto('{raw}/{f}.csv', header=true, sample_size=-1)")

def q(sql):
    return con.execute(sql).fetchdf()

print("=== ROW COUNTS, COLUMNS, NULLS, EXACT DUPLICATES ===")
for f in files:
    t = f"raw_{f}"
    n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    dup = con.execute(f"SELECT COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM {t})) FROM {t}").fetchone()[0]
    print(f"\n{f}: {n:,} rows | exact duplicate rows: {dup:,}")
    for col, typ, *_ in con.execute(f"DESCRIBE {t}").fetchall():
        nulls = con.execute(f'SELECT COUNT(*) FROM {t} WHERE "{col}" IS NULL').fetchone()[0]
        blanks = con.execute(f'SELECT COUNT(*) FROM {t} WHERE TRIM(CAST("{col}" AS VARCHAR)) = \'\'').fetchone()[0]
        nd = con.execute(f'SELECT COUNT(DISTINCT "{col}") FROM {t}').fetchone()[0]
        print(f"   {col:<22} {typ:<8} nulls={nulls:<6,} blanks={blanks:<6,} distinct={nd:,}")

print("\n=== TRANSACTION_DATA: VALUE CHECKS ===")
print(q("""SELECT MIN(DAY) min_day, MAX(DAY) max_day, MIN(WEEK_NO) min_wk, MAX(WEEK_NO) max_wk,
          COUNT(DISTINCT DAY) n_days, COUNT(DISTINCT WEEK_NO) n_weeks,
          COUNT(DISTINCT household_key) n_hh, COUNT(DISTINCT BASKET_ID) n_baskets,
          COUNT(DISTINCT PRODUCT_ID) n_products, COUNT(DISTINCT STORE_ID) n_stores,
          ROUND(SUM(SALES_VALUE),2) total_sales, SUM(QUANTITY) total_units,
          ROUND(SUM(RETAIL_DISC),2) retail_disc, ROUND(SUM(COUPON_DISC),2) coupon_disc,
          ROUND(SUM(COUPON_MATCH_DISC),2) coupon_match_disc,
          MIN(TRANS_TIME) min_time, MAX(TRANS_TIME) max_time
       FROM raw_transaction_data""").T.to_string())

checks = {
 "QUANTITY = 0": "QUANTITY = 0",
 "QUANTITY < 0": "QUANTITY < 0",
 "SALES_VALUE = 0": "SALES_VALUE = 0",
 "SALES_VALUE < 0": "SALES_VALUE < 0",
 "QUANTITY = 0 AND SALES_VALUE > 0": "QUANTITY = 0 AND SALES_VALUE > 0",
 "QUANTITY > 0 AND SALES_VALUE = 0": "QUANTITY > 0 AND SALES_VALUE = 0",
 "QUANTITY = 0 AND SALES_VALUE = 0": "QUANTITY = 0 AND SALES_VALUE = 0",
 "RETAIL_DISC > 0 (positive discount, sign anomaly)": "RETAIL_DISC > 0",
 "COUPON_DISC > 0 (sign anomaly)": "COUPON_DISC > 0",
 "COUPON_MATCH_DISC > 0 (sign anomaly)": "COUPON_MATCH_DISC > 0",
 "COUPON_DISC < 0 (coupon used)": "COUPON_DISC < 0",
 "COUPON_MATCH_DISC < 0": "COUPON_MATCH_DISC < 0",
 "QUANTITY > 100 (bulk/odd units)": "QUANTITY > 100",
 "QUANTITY > 1000": "QUANTITY > 1000",
 "SALES_VALUE > 100": "SALES_VALUE > 100",
 "TRANS_TIME minutes >= 60 (invalid HHMM)": "CAST(TRANS_TIME AS INT) % 100 >= 60",
 "CAST(TRANS_TIME AS INT) > 2359 OR LENGTH(TRANS_TIME)<>4": "CAST(TRANS_TIME AS INT) > 2359 OR LENGTH(TRANS_TIME)<>4",
}
for label, cond in checks.items():
    r = con.execute(f"SELECT COUNT(*), ROUND(SUM(SALES_VALUE),2), SUM(QUANTITY) FROM raw_transaction_data WHERE {cond}").fetchone()
    print(f"   {label:<52} rows={r[0]:>10,}  sales={r[1]}  units={r[2]}")

print("\n-- Duplicates on business key (BASKET_ID, PRODUCT_ID) --")
print(q("""SELECT COUNT(*) dup_groups, SUM(c) rows_in_groups, SUM(c-1) extra_rows FROM
           (SELECT BASKET_ID, PRODUCT_ID, COUNT(*) c FROM raw_transaction_data GROUP BY 1,2 HAVING COUNT(*)>1)""").to_string())

print("\n-- Basket consistency: baskets with >1 household / day / store --")
print(q("""SELECT SUM(CASE WHEN nh>1 THEN 1 END) multi_hh, SUM(CASE WHEN nd>1 THEN 1 END) multi_day,
                  SUM(CASE WHEN ns>1 THEN 1 END) multi_store, SUM(CASE WHEN nw>1 THEN 1 END) multi_week FROM
           (SELECT BASKET_ID, COUNT(DISTINCT household_key) nh, COUNT(DISTINCT DAY) nd,
                   COUNT(DISTINCT STORE_ID) ns, COUNT(DISTINCT WEEK_NO) nw FROM raw_transaction_data GROUP BY 1)""").to_string())

print("\n-- DAY -> WEEK_NO mapping consistency (should be 1 week per day) --")
print(q("""SELECT COUNT(*) days_with_multiple_weeks FROM
           (SELECT DAY FROM raw_transaction_data GROUP BY DAY HAVING COUNT(DISTINCT WEEK_NO)>1)""").to_string())
print(q("""SELECT WEEK_NO, MIN(DAY) first_day, MAX(DAY) last_day, COUNT(DISTINCT DAY) n_days,
                  COUNT(*) n_rows, ROUND(SUM(SALES_VALUE),2) sales, COUNT(DISTINCT household_key) n_hh
           FROM raw_transaction_data GROUP BY 1 ORDER BY 1""").to_string())

print("\n-- Missing days in the DAY sequence --")
print(q("""SELECT d.day AS missing_day FROM range(1, (SELECT MAX(DAY)+1 FROM raw_transaction_data)) d(day)
           WHERE d.day NOT IN (SELECT DISTINCT DAY FROM raw_transaction_data)""").to_string())

print("\n=== KEY MATCHING ===")
kchecks = {
 "transactions whose PRODUCT_ID not in product":
   "SELECT COUNT(*) FROM raw_transaction_data t WHERE NOT EXISTS (SELECT 1 FROM raw_product p WHERE p.PRODUCT_ID=t.PRODUCT_ID)",
 "distinct households in transactions":
   "SELECT COUNT(DISTINCT household_key) FROM raw_transaction_data",
 "transaction households WITHOUT demographics":
   "SELECT COUNT(DISTINCT household_key) FROM raw_transaction_data WHERE household_key NOT IN (SELECT household_key FROM raw_hh_demographic)",
 "transaction rows from households WITHOUT demographics":
   "SELECT COUNT(*) FROM raw_transaction_data WHERE household_key NOT IN (SELECT household_key FROM raw_hh_demographic)",
 "sales from households WITHOUT demographics":
   "SELECT ROUND(SUM(SALES_VALUE),2) FROM raw_transaction_data WHERE household_key NOT IN (SELECT household_key FROM raw_hh_demographic)",
 "demographic households with no transactions":
   "SELECT COUNT(*) FROM raw_hh_demographic WHERE household_key NOT IN (SELECT household_key FROM raw_transaction_data)",
 "products never sold":
   "SELECT COUNT(*) FROM raw_product WHERE PRODUCT_ID NOT IN (SELECT DISTINCT PRODUCT_ID FROM raw_transaction_data)",
 "campaign_table campaigns not in campaign_desc":
   "SELECT COUNT(*) FROM raw_campaign_table WHERE CAMPAIGN NOT IN (SELECT CAMPAIGN FROM raw_campaign_desc)",
 "campaign_table rows: DESCRIPTION differs from campaign_desc":
   "SELECT COUNT(*) FROM raw_campaign_table t JOIN raw_campaign_desc d USING (CAMPAIGN) WHERE t.DESCRIPTION<>d.DESCRIPTION",
 "campaign_table households not in transactions":
   "SELECT COUNT(DISTINCT household_key) FROM raw_campaign_table WHERE household_key NOT IN (SELECT household_key FROM raw_transaction_data)",
 "coupon rows whose PRODUCT_ID not in product":
   "SELECT COUNT(*) FROM raw_coupon WHERE PRODUCT_ID NOT IN (SELECT PRODUCT_ID FROM raw_product)",
 "coupon campaigns not in campaign_desc":
   "SELECT COUNT(*) FROM raw_coupon WHERE CAMPAIGN NOT IN (SELECT CAMPAIGN FROM raw_campaign_desc)",
 "redemptions: (COUPON_UPC,CAMPAIGN) not in coupon":
   "SELECT COUNT(*) FROM raw_coupon_redempt r WHERE NOT EXISTS (SELECT 1 FROM raw_coupon c WHERE c.COUPON_UPC=r.COUPON_UPC AND c.CAMPAIGN=r.CAMPAIGN)",
 "redemptions: household not targeted by that campaign (not in campaign_table)":
   "SELECT COUNT(*) FROM raw_coupon_redempt r WHERE NOT EXISTS (SELECT 1 FROM raw_campaign_table c WHERE c.household_key=r.household_key AND c.CAMPAIGN=r.CAMPAIGN)",
 "redemptions: DAY outside the campaign's START_DAY-END_DAY window":
   "SELECT COUNT(*) FROM raw_coupon_redempt r JOIN raw_campaign_desc d USING (CAMPAIGN) WHERE r.DAY<d.START_DAY OR r.DAY>d.END_DAY",
 "redemptions: household not in transactions":
   "SELECT COUNT(*) FROM raw_coupon_redempt WHERE household_key NOT IN (SELECT household_key FROM raw_transaction_data)",
 "campaign_desc: campaigns with START_DAY > END_DAY":
   "SELECT COUNT(*) FROM raw_campaign_desc WHERE START_DAY > END_DAY",
 "campaign_desc: campaigns starting before day 1 / ending after last txn day":
   "SELECT COUNT(*) FROM raw_campaign_desc WHERE START_DAY<1 OR END_DAY>(SELECT MAX(DAY) FROM raw_transaction_data)",
}
for label, sql in kchecks.items():
    print(f"   {label:<78} {con.execute(sql).fetchone()[0]}")

print("\n=== PRODUCT TABLE CHECKS ===")
print(q("""SELECT DEPARTMENT, COUNT(*) n FROM raw_product GROUP BY 1 ORDER BY n DESC""").to_string())
print(q("""SELECT BRAND, COUNT(*) n FROM raw_product GROUP BY 1""").to_string())
for label, cond in {
  "blank DEPARTMENT": "TRIM(DEPARTMENT)=''",
  "COMMODITY_DESC = 'NO COMMODITY DESCRIPTION' or blank": "COMMODITY_DESC='NO COMMODITY DESCRIPTION' OR TRIM(COMMODITY_DESC)=''",
  "SUB_COMMODITY_DESC = 'NO SUBCOMMODITY DESCRIPTION' or blank": "SUB_COMMODITY_DESC='NO SUBCOMMODITY DESCRIPTION' OR TRIM(SUB_COMMODITY_DESC)=''",
  "blank CURR_SIZE_OF_PRODUCT": "CURR_SIZE_OF_PRODUCT IS NULL OR TRIM(CURR_SIZE_OF_PRODUCT)=''",
}.items():
    print(f"   {label:<60} {con.execute(f'SELECT COUNT(*) FROM raw_product WHERE {cond}').fetchone()[0]:,}")
print("   duplicate PRODUCT_ID:", con.execute("SELECT COUNT(*)-COUNT(DISTINCT PRODUCT_ID) FROM raw_product").fetchone()[0])

print("\n=== HH_DEMOGRAPHIC: VALUE DISTRIBUTIONS ===")
print("   duplicate household_key:", con.execute("SELECT COUNT(*)-COUNT(DISTINCT household_key) FROM raw_hh_demographic").fetchone()[0])
for c in ["AGE_DESC","MARITAL_STATUS_CODE","INCOME_DESC","HOMEOWNER_DESC","HH_COMP_DESC","HOUSEHOLD_SIZE_DESC","KID_CATEGORY_DESC"]:
    d = con.execute(f"SELECT {c}, COUNT(*) FROM raw_hh_demographic GROUP BY 1 ORDER BY 1").fetchall()
    print(f"   {c}: " + ", ".join(f"{k}={v}" for k, v in d))
print("   HH_COMP says 'No Kids'/Single but KID_CATEGORY is a number:",
      con.execute("SELECT COUNT(*) FROM raw_hh_demographic WHERE (HH_COMP_DESC LIKE '%No Kids' OR HH_COMP_DESC LIKE 'Single%') AND KID_CATEGORY_DESC<>'None/Unknown'").fetchone()[0])
print("   HH_COMP says Kids but KID_CATEGORY = None/Unknown:",
      con.execute("SELECT COUNT(*) FROM raw_hh_demographic WHERE HH_COMP_DESC LIKE '%Kids' AND HH_COMP_DESC NOT LIKE '%No Kids' AND KID_CATEGORY_DESC='None/Unknown'").fetchone()[0])
print("   'Single' household but HOUSEHOLD_SIZE >= 2:",
      con.execute("SELECT COUNT(*) FROM raw_hh_demographic WHERE HH_COMP_DESC LIKE 'Single%' AND HOUSEHOLD_SIZE_DESC<>'1'").fetchone()[0])

print("\n=== CAMPAIGN / COUPON SUMMARY ===")
print(q("SELECT DESCRIPTION, COUNT(*) n_campaigns, MIN(START_DAY) min_start, MAX(END_DAY) max_end FROM raw_campaign_desc GROUP BY 1 ORDER BY 1").to_string())
print("   campaign_table duplicate (household,campaign):",
      con.execute("SELECT COUNT(*)-(SELECT COUNT(*) FROM (SELECT DISTINCT household_key,CAMPAIGN FROM raw_campaign_table)) FROM raw_campaign_table").fetchone()[0])
print("   coupon_redempt exact duplicate rows:",
      con.execute("SELECT COUNT(*)-(SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw_coupon_redempt)) FROM raw_coupon_redempt").fetchone()[0])
print("   same COUPON_UPC redeemed same day by same hh under 2 campaigns:",
      con.execute("SELECT COUNT(*) FROM (SELECT household_key,DAY,COUPON_UPC FROM raw_coupon_redempt GROUP BY 1,2,3 HAVING COUNT(DISTINCT CAMPAIGN)>1)").fetchone()[0])
print("   COUPON_UPCs mapped to >1 campaign in coupon table:",
      con.execute("SELECT COUNT(*) FROM (SELECT COUPON_UPC FROM raw_coupon GROUP BY 1 HAVING COUNT(DISTINCT CAMPAIGN)>1)").fetchone()[0])
print("   transaction rows with COUPON_DISC<0 vs redemption rows:",
      con.execute("SELECT COUNT(*) FROM raw_transaction_data WHERE COUPON_DISC<0").fetchone()[0], "vs",
      con.execute("SELECT COUNT(*) FROM raw_coupon_redempt").fetchone()[0])
con.close()
