"""Step 1c - follow-up checks. Usage: python3 01c_followups.py <db_path>"""
import sys, duckdb
con = duckdb.connect(sys.argv[1]); q = lambda s: con.execute(s).fetchdf().to_string()
print("Causal duplicate keys: exact duplicates vs conflicting flags")
print(q("""SELECT COUNT(*) dup_keys, SUM(CASE WHEN nflag=1 THEN 1 ELSE 0 END) identical_flags,
                  SUM(CASE WHEN nflag>1 THEN 1 ELSE 0 END) conflicting_flags, SUM(n-1) extra_rows FROM
           (SELECT PRODUCT_ID,STORE_ID,WEEK_NO, COUNT(*) n, COUNT(DISTINCT display||'|'||mailer) nflag
            FROM raw_causal_data GROUP BY 1,2,3 HAVING COUNT(*)>1)"""))
print("Exact duplicate causal rows:", con.execute("SELECT COUNT(*)-(SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw_causal_data)) FROM raw_causal_data").fetchone()[0])
print("\nTransaction coverage by causal using DISTINCT causal keys (no fan-out):")
print(q("""WITH ck AS (SELECT DISTINCT PRODUCT_ID,STORE_ID,WEEK_NO FROM raw_causal_data)
           SELECT CASE WHEN ck.PRODUCT_ID IS NULL THEN 'no causal row' ELSE 'has causal row' END status,
                  COUNT(*) txn_rows, ROUND(SUM(t.SALES_VALUE),2) sales,
                  ROUND(100.0*SUM(t.SALES_VALUE)/SUM(SUM(t.SALES_VALUE)) OVER (),2) pct_sales
           FROM raw_transaction_data t LEFT JOIN ck USING (PRODUCT_ID,STORE_ID,WEEK_NO) GROUP BY 1"""))
print("\nCoverage restricted to causal stores (115) and weeks 9-101:")
print(q("""WITH ck AS (SELECT DISTINCT PRODUCT_ID,STORE_ID,WEEK_NO FROM raw_causal_data),
           cs AS (SELECT DISTINCT STORE_ID FROM raw_causal_data)
           SELECT COUNT(*) txn_rows, ROUND(SUM(t.SALES_VALUE),2) sales,
                  ROUND(100.0*SUM(t.SALES_VALUE)/(SELECT SUM(SALES_VALUE) FROM raw_transaction_data),2) pct_total_sales,
                  ROUND(100.0*SUM(CASE WHEN ck.PRODUCT_ID IS NOT NULL THEN t.SALES_VALUE END)/SUM(t.SALES_VALUE),2) pct_matched_within
           FROM raw_transaction_data t JOIN cs USING (STORE_ID)
           LEFT JOIN ck USING (PRODUCT_ID,STORE_ID,WEEK_NO) WHERE t.WEEK_NO BETWEEN 9 AND 101"""))
print("\nUnits split: fuel-like 'COUPON/MISC ITEMS' (KIOSK-GAS + MISC SALES TRAN) vs everything else")
print(q("""SELECT CASE WHEN p.COMMODITY_DESC='COUPON/MISC ITEMS' AND p.DEPARTMENT IN ('KIOSK-GAS','MISC SALES TRAN') THEN 'COUPON/MISC ITEMS (gas/misc)' ELSE 'all other' END grp,
                  COUNT(*) n_rows, SUM(t.QUANTITY) units, ROUND(SUM(t.SALES_VALUE),2) sales
           FROM raw_transaction_data t JOIN raw_product p USING (PRODUCT_ID) GROUP BY 1"""))
print("\nPositive RETAIL_DISC: real (>=0.005) vs float noise (<0.005)")
print(q("""SELECT CASE WHEN RETAIL_DISC>=0.005 THEN 'real >= 0.005' ELSE 'noise < 0.005' END k, COUNT(*) n, ROUND(SUM(RETAIL_DISC),2) amt
           FROM raw_transaction_data WHERE RETAIL_DISC>0 GROUP BY 1"""))
print("Discount columns with tiny float residues (|x| between 0 and 0.005):",
      con.execute("SELECT COUNT(*) FROM raw_transaction_data WHERE (ABS(RETAIL_DISC)>0 AND ABS(RETAIL_DISC)<0.005) OR (ABS(COUPON_DISC)>0 AND ABS(COUPON_DISC)<0.005) OR (ABS(COUPON_MATCH_DISC)>0 AND ABS(COUPON_MATCH_DISC)<0.005)").fetchone()[0])
print("\nBlank-department products: rows, sales, units in transactions")
print(q("SELECT COUNT(*) n_rows, SUM(t.SALES_VALUE) sales, SUM(t.QUANTITY) units FROM raw_transaction_data t JOIN raw_product p USING (PRODUCT_ID) WHERE TRIM(p.DEPARTMENT)=''"))
print("\nPartial weeks: week 1 (days 1-5) and 102 (days 706-711) households vs median week")
print(q("SELECT MEDIAN(n_hh) med_hh, MEDIAN(sales) med_sales FROM (SELECT WEEK_NO, COUNT(DISTINCT household_key) n_hh, SUM(SALES_VALUE) sales FROM raw_transaction_data WHERE WEEK_NO BETWEEN 17 AND 101 GROUP BY 1)"))
print("\nBaskets with zero total sales:", con.execute("SELECT COUNT(*) FROM (SELECT BASKET_ID FROM raw_transaction_data GROUP BY 1 HAVING SUM(SALES_VALUE)=0)").fetchone()[0])
print("Coupon table: rows after removing exact duplicates:", con.execute("SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw_coupon)").fetchone()[0])
