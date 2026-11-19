"""Step 1b - Profile causal_data (full scan, streamed by DuckDB - no sampling)
and deep-dive on issues found in 01_profile.py.
Usage: python3 01b_profile_causal_and_deepdive.py <causal_csv> <db_path>"""
import sys, duckdb

causal_csv, db = sys.argv[1], sys.argv[2]
con = duckdb.connect(db)
con.execute("SET memory_limit='3GB'")
# Stored as a DuckDB table (columnar, compressed); the CSV is read in streamed chunks.
con.execute(f"CREATE OR REPLACE TABLE raw_causal_data AS SELECT * FROM read_csv_auto('{causal_csv}', header=true, sample_size=-1)")
q = lambda s: con.execute(s).fetchdf().to_string()

print("=== CAUSAL_DATA ===")
print("rows:", f"{con.execute('SELECT COUNT(*) FROM raw_causal_data').fetchone()[0]:,}")
for col, typ, *_ in con.execute("DESCRIBE raw_causal_data").fetchall():
    nulls = con.execute(f'SELECT COUNT(*) FROM raw_causal_data WHERE "{col}" IS NULL').fetchone()[0]
    nd = con.execute(f'SELECT COUNT(DISTINCT "{col}") FROM raw_causal_data').fetchone()[0]
    print(f"   {col:<12} {typ:<8} nulls={nulls:,} distinct={nd:,}")
print("duplicate (PRODUCT_ID, STORE_ID, WEEK_NO):",
      con.execute("SELECT COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT PRODUCT_ID,STORE_ID,WEEK_NO FROM raw_causal_data)) FROM raw_causal_data").fetchone()[0])
print(q("SELECT MIN(WEEK_NO) min_wk, MAX(WEEK_NO) max_wk, COUNT(DISTINCT WEEK_NO) n_wk, COUNT(DISTINCT STORE_ID) n_store, COUNT(DISTINCT PRODUCT_ID) n_prod FROM raw_causal_data"))
print(q("SELECT display, COUNT(*) n FROM raw_causal_data GROUP BY 1 ORDER BY 1"))
print(q("SELECT mailer, COUNT(*) n FROM raw_causal_data GROUP BY 1 ORDER BY 1"))
print("causal PRODUCT_ID not in product:",
      con.execute("SELECT COUNT(*) FROM raw_causal_data c WHERE NOT EXISTS (SELECT 1 FROM raw_product p WHERE p.PRODUCT_ID=c.PRODUCT_ID)").fetchone()[0])
print("causal STORE_IDs not seen in transactions:",
      con.execute("SELECT COUNT(DISTINCT STORE_ID) FROM raw_causal_data WHERE STORE_ID NOT IN (SELECT DISTINCT STORE_ID FROM raw_transaction_data)").fetchone()[0])
print("transaction STORE_IDs with no causal rows:",
      con.execute("SELECT COUNT(DISTINCT STORE_ID) FROM raw_transaction_data WHERE STORE_ID NOT IN (SELECT DISTINCT STORE_ID FROM raw_causal_data)").fetchone()[0])
print("weeks in transactions with no causal rows:",
      con.execute("SELECT LIST(DISTINCT WEEK_NO ORDER BY WEEK_NO) FROM raw_transaction_data WHERE WEEK_NO NOT IN (SELECT DISTINCT WEEK_NO FROM raw_causal_data)").fetchone()[0])
print("\nTransaction coverage by causal (match on PRODUCT_ID, STORE_ID, WEEK_NO):")
print(q("""SELECT CASE WHEN c.PRODUCT_ID IS NULL THEN 'no causal row' ELSE 'has causal row' END AS status,
                  COUNT(*) txn_rows, ROUND(SUM(t.SALES_VALUE),2) sales,
                  ROUND(100.0*SUM(t.SALES_VALUE)/SUM(SUM(t.SALES_VALUE)) OVER (),2) pct_sales
           FROM raw_transaction_data t
           LEFT JOIN raw_causal_data c ON c.PRODUCT_ID=t.PRODUCT_ID AND c.STORE_ID=t.STORE_ID AND c.WEEK_NO=t.WEEK_NO
           GROUP BY 1"""))
print("Causal rows per week (first/last 5):")
print(q("SELECT WEEK_NO, COUNT(*) n FROM raw_causal_data GROUP BY 1 ORDER BY 1 LIMIT 5"))
print(q("SELECT WEEK_NO, COUNT(*) n FROM raw_causal_data GROUP BY 1 ORDER BY 1 DESC LIMIT 5"))

print("\n=== DEEP DIVE: QUANTITY > 1000 rows by department/commodity ===")
print(q("""SELECT p.DEPARTMENT, p.COMMODITY_DESC, COUNT(*) n_rows, SUM(t.QUANTITY) units,
                  ROUND(SUM(t.SALES_VALUE),2) sales, MEDIAN(t.QUANTITY) median_qty
           FROM raw_transaction_data t JOIN raw_product p USING (PRODUCT_ID)
           WHERE t.QUANTITY > 1000 GROUP BY 1,2 ORDER BY units DESC LIMIT 10"""))
print("\nKIOSK-GAS / fuel products, all rows:")
print(q("""SELECT p.DEPARTMENT, p.COMMODITY_DESC, COUNT(*) n_rows, SUM(t.QUANTITY) units, ROUND(SUM(t.SALES_VALUE),2) sales
           FROM raw_transaction_data t JOIN raw_product p USING (PRODUCT_ID)
           WHERE p.DEPARTMENT='KIOSK-GAS' OR p.COMMODITY_DESC ILIKE '%GASOLINE%' OR p.COMMODITY_DESC ILIKE '%FUEL%'
           GROUP BY 1,2 ORDER BY units DESC"""))
print("\nQUANTITY 101-1000 rows by department (top 10):")
print(q("""SELECT p.DEPARTMENT, COUNT(*) n_rows, SUM(t.QUANTITY) units, ROUND(SUM(t.SALES_VALUE),2) sales
           FROM raw_transaction_data t JOIN raw_product p USING (PRODUCT_ID)
           WHERE t.QUANTITY BETWEEN 101 AND 1000 GROUP BY 1 ORDER BY n_rows DESC LIMIT 10"""))

print("\n=== DEEP DIVE: sales by department, incl. non-merchandise ===")
print(q("""SELECT COALESCE(NULLIF(TRIM(p.DEPARTMENT),''),'(blank)') dept, COUNT(*) n_rows,
                  ROUND(SUM(t.SALES_VALUE),2) sales, ROUND(100*SUM(t.SALES_VALUE)/(SELECT SUM(SALES_VALUE) FROM raw_transaction_data),3) pct_sales
           FROM raw_transaction_data t JOIN raw_product p USING (PRODUCT_ID)
           GROUP BY 1 ORDER BY sales DESC"""))
print("\nRows whose product has COMMODITY 'NO COMMODITY DESCRIPTION' or blank:")
print(q("""SELECT COUNT(*) n_rows, ROUND(SUM(t.SALES_VALUE),2) sales FROM raw_transaction_data t JOIN raw_product p USING (PRODUCT_ID)
           WHERE p.COMMODITY_DESC='NO COMMODITY DESCRIPTION' OR TRIM(p.COMMODITY_DESC)=''"""))
print("\nZero-quantity & zero-sales rows by department (top 8):")
print(q("""SELECT p.DEPARTMENT, COUNT(*) n_rows FROM raw_transaction_data t JOIN raw_product p USING (PRODUCT_ID)
           WHERE t.QUANTITY=0 AND t.SALES_VALUE=0 GROUP BY 1 ORDER BY 2 DESC LIMIT 8"""))
print("\nPositive RETAIL_DISC rows (sample):")
print(q("SELECT household_key, BASKET_ID, PRODUCT_ID, QUANTITY, SALES_VALUE, RETAIL_DISC FROM raw_transaction_data WHERE RETAIL_DISC>0 LIMIT 5"))
print("\nSALES_VALUE > 100: top 5 rows")
print(q("""SELECT t.PRODUCT_ID, p.DEPARTMENT, p.COMMODITY_DESC, t.QUANTITY, t.SALES_VALUE FROM raw_transaction_data t
           JOIN raw_product p USING (PRODUCT_ID) ORDER BY t.SALES_VALUE DESC LIMIT 5"""))

print("\n=== DEEP DIVE: household onboarding over time ===")
print(q("""SELECT first_week_bucket, COUNT(*) n_households FROM (
             SELECT household_key, CASE WHEN MIN(WEEK_NO)<=4 THEN 'wk 1-4' WHEN MIN(WEEK_NO)<=8 THEN 'wk 5-8'
                    WHEN MIN(WEEK_NO)<=16 THEN 'wk 9-16' ELSE 'wk 17+' END first_week_bucket
             FROM raw_transaction_data GROUP BY 1) GROUP BY 1 ORDER BY 1"""))
print("Households with < 5 baskets in the 2 years:",
      con.execute("SELECT COUNT(*) FROM (SELECT household_key FROM raw_transaction_data GROUP BY 1 HAVING COUNT(DISTINCT BASKET_ID)<5)").fetchone()[0])
print("Households whose last purchase is before week 90:",
      con.execute("SELECT COUNT(*) FROM (SELECT household_key FROM raw_transaction_data GROUP BY 1 HAVING MAX(WEEK_NO)<90)").fetchone()[0])

print("\n=== DEEP DIVE: coupons ===")
print("Redemption pairs on same hh/day/UPC under 2 campaigns (rows involved):",
      con.execute("""SELECT COUNT(*) FROM raw_coupon_redempt r JOIN (SELECT household_key,DAY,COUPON_UPC FROM raw_coupon_redempt
                     GROUP BY 1,2,3 HAVING COUNT(DISTINCT CAMPAIGN)>1) d USING (household_key,DAY,COUPON_UPC)""").fetchone()[0])
print("Redemptions where hh has NO transaction row with COUPON_DISC<0 on that DAY:",
      con.execute("""SELECT COUNT(*) FROM raw_coupon_redempt r WHERE NOT EXISTS (SELECT 1 FROM raw_transaction_data t
                     WHERE t.household_key=r.household_key AND t.DAY=r.DAY AND t.COUPON_DISC<0)""").fetchone()[0])
print("Campaigns with zero redemptions:",
      con.execute("SELECT COUNT(*) FROM raw_campaign_desc WHERE CAMPAIGN NOT IN (SELECT DISTINCT CAMPAIGN FROM raw_coupon_redempt)").fetchone()[0])
print(q("SELECT CAMPAIGN, DESCRIPTION, START_DAY, END_DAY FROM raw_campaign_desc WHERE END_DAY > 711"))
con.close()
