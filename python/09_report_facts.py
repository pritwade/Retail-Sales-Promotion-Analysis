"""Collect every number used in the report into report_facts.json (computed, never typed).
Usage: python3 09_report_facts.py <db_path> <results_dir>"""
import sys, json, duckdb, pandas as pd
db, res = sys.argv[1], sys.argv[2]
con = duckdb.connect(db, read_only=True); one = lambda s: con.execute(s).fetchone()[0]
R = lambda n: pd.read_csv(f"{res}/{n}.csv")
k = R("r_kpi_overview").iloc[0]; ps = R("r_period_summary").set_index("period")
dept = R("r_department"); brand = R("r_brand").set_index("BRAND"); com = R("r_commodity")
lift = R("r_promo_lift").set_index("promo_status"); disc = R("r_promo_discount").set_index("promo_status")
scope = R("r_promo_scope").set_index("promo_status"); ctype = R("r_campaign_type").set_index("campaign_type")
camp = R("r_campaign"); ct = R("r_coupon_totals").iloc[0]; rs = R("r_campaign_redeemer_spend").set_index("grp")
seg = R("r_rfm_segment").set_index("segment"); demo = R("r_rfm_demo").set_index("segment")
acc = R("r_forecast_accuracy"); fwd = R("r_forecast_forward"); ret = R("r_hh_retention"); rep = R("r_commodity_repeat")
recon = R("../clean/reconciliation") if False else pd.read_csv(f"{res}/../clean/reconciliation.csv").set_index("metric")
log = pd.read_csv(f"{res}/../clean/cleaning_log.csv").set_index("rule_id")
y1, y2 = ps.loc["b) Weeks 24-49 (year 1 window)"], ps.loc["c) Weeks 76-101 (year 2 window)"]
fx = acc[acc["mode"] == "fixed origin (wk 89)"].set_index("method")
best = fx.index[0]
causal_cov = one("""WITH ck AS (SELECT DISTINCT PRODUCT_ID,STORE_ID,WEEK_NO FROM clean_causal)
   SELECT SUM(CASE WHEN ck.PRODUCT_ID IS NOT NULL THEN t.SALES_VALUE END)/SUM(t.SALES_VALUE)*100
   FROM clean_transactions t LEFT JOIN ck USING (PRODUCT_ID,STORE_ID,WEEK_NO)""")
f = {
 # raw profile
 "raw_txn_rows": one("SELECT COUNT(*) FROM raw_transaction_data"), "raw_sales": round(one("SELECT SUM(SALES_VALUE) FROM raw_transaction_data"), 2),
 "raw_units": one("SELECT SUM(QUANTITY) FROM raw_transaction_data"), "raw_causal_rows": one("SELECT COUNT(*) FROM raw_causal_data"),
 "n_products": one("SELECT COUNT(*) FROM raw_product"), "n_demo": one("SELECT COUNT(*) FROM raw_hh_demographic"),
 "n_campaigns": one("SELECT COUNT(*) FROM raw_campaign_desc"), "n_coupon_rows": one("SELECT COUNT(*) FROM raw_coupon"),
 "n_redemptions": one("SELECT COUNT(*) FROM raw_coupon_redempt"), "n_campaign_table": one("SELECT COUNT(*) FROM raw_campaign_table"),
 "n_stores": one("SELECT COUNT(DISTINCT STORE_ID) FROM raw_transaction_data"), "n_causal_stores": one("SELECT COUNT(DISTINCT STORE_ID) FROM raw_causal_data"),
 "fuel_units": one("SELECT SUM(t.QUANTITY) FROM raw_transaction_data t JOIN raw_product p USING (PRODUCT_ID) WHERE p.COMMODITY_DESC='COUPON/MISC ITEMS' AND p.DEPARTMENT IN ('KIOSK-GAS','MISC SALES TRAN')"),
 "fuel_rows": one("SELECT COUNT(*) FROM raw_transaction_data t JOIN raw_product p USING (PRODUCT_ID) WHERE p.COMMODITY_DESC='COUPON/MISC ITEMS' AND p.DEPARTMENT IN ('KIOSK-GAS','MISC SALES TRAN')"),
 "nodemo_hh": one("SELECT COUNT(DISTINCT household_key) FROM raw_transaction_data WHERE household_key NOT IN (SELECT household_key FROM raw_hh_demographic)"),
 "nodemo_sales": round(one("SELECT SUM(SALES_VALUE) FROM raw_transaction_data WHERE household_key NOT IN (SELECT household_key FROM raw_hh_demographic)"), 2),
 "causal_dup_keys": int(log.loc["K1", "rows_affected"]), "causal_cov_pct": round(causal_cov, 2),
 "zero_zero_rows": one("SELECT COUNT(*) FROM raw_transaction_data WHERE QUANTITY=0 AND SALES_VALUE=0"),
 "single_inconsistent": int(log.loc["D1", "rows_affected"]), "coupon_dups": int(log.loc["C1", "rows_affected"]),
 "multi_campaign_redemptions": int(log.loc["C2", "rows_affected"]), "blank_size": int(log.loc["P3", "rows_affected"]),
 # cleaning
 "t1_removed": int(log.loc["T1", "rows_affected"]), "t1b_rows": int(log.loc["T1b", "rows_affected"]),
 "t1b_coupon": round(-one("SELECT SUM(COUPON_DISC) FROM clean_transactions WHERE is_discount_only_line=1"), 2),
 "nonmerch_rows": int(log.loc["T2", "rows_affected"]), "nonmerch_sales": float(log.loc["T2", "sales_affected"]),
 "clean_rows": int(recon.loc["rows", "after_clean"]), "baskets_removed": int(-recon.loc["baskets", "diff"]),
 "sales_diff": float(recon.loc["sales", "diff"]),
 # KPIs
 **{f"k_{c}": (float(k[c]) if c not in ("baskets", "households", "merch_units") else int(k[c])) for c in k.index},
 "y1_sales": float(y1.sales), "y2_sales": float(y2.sales), "y1_hh": float(y1.avg_weekly_active_hh), "y2_hh": float(y2.avg_weekly_active_hh),
 "y2_growth_pct": round((y2.sales / y1.sales - 1) * 100, 2), "hh_growth_pct": round((y2.avg_weekly_active_hh / y1.avg_weekly_active_hh - 1) * 100, 2),
 "ramp_avg_hh": float(ps.loc["a) Weeks 1-16 (ramp-up)"].avg_weekly_active_hh),
 "retention_avg": round(ret[ret.period >= 5].retention_pct.mean(), 2),
 "repeat_median": round(rep[rep.buyers >= 500].repeat_rate_pct.median(), 2), "repeat_n": int((rep.buyers >= 500).sum()),
 # merchandising
 "dept": dept[dept.is_merch == 1].head(6)[["DEPARTMENT", "sales", "pct_merch_sales", "private_label_pct", "growth_y2_vs_y1_pct", "retail_disc_depth_pct"]].to_dict("records"),
 "kiosk_gas_pct": float(dept.set_index("DEPARTMENT").loc["KIOSK-GAS", "pct_total_sales"]),
 "top3_dept_pct": round(dept[dept.is_merch == 1].head(3).pct_merch_sales.sum(), 2),
 "pl_share": float(brand.loc["Private", "pct_merch_sales"]), "pl_price": float(brand.loc["Private", "avg_price_per_unit"]),
 "nb_price": float(brand.loc["National", "avg_price_per_unit"]), "pl_units_share": round(brand.loc["Private", "units"] / brand.units.sum() * 100, 2),
 "top10": R("r_commodity_top10")[["COMMODITY_DESC", "DEPARTMENT", "sales", "pct_merch_sales", "private_label_pct", "growth_pct"]].to_dict("records"),
 "top10_share": round(R("r_commodity_top10").pct_merch_sales.sum(), 2),
 "growers": R("r_commodity_growers").head(5)[["COMMODITY_DESC", "DEPARTMENT", "sales_wk24_49", "sales_wk76_101", "growth_pct"]].to_dict("records"),
 "decliners": R("r_commodity_decliners").head(5)[["COMMODITY_DESC", "DEPARTMENT", "sales_wk24_49", "sales_wk76_101", "growth_pct"]].to_dict("records"),
 "n_commodities": int(len(com)),
 # promotions
 "lift": {s: {c: float(lift.loc[s, c]) for c in ["matched_product_store_pairs", "unit_lift_pct", "sales_lift_pct", "gross_value_lift_pct"]} for s in lift.index},
 "disc": {s: {c: float(disc.loc[s, c]) for c in disc.columns} for s in disc.index},
 "scope": {s: float(scope.loc[s, "pct_sales"]) for s in scope.index},
 "lift_dept": R("r_promo_lift_dept").to_dict("records"),
 # campaigns
 "ctype": {t: {c: float(ctype.loc[t, c]) for c in ctype.columns} for t in ctype.index},
 "camp_top": camp.head(3)[["CAMPAIGN", "campaign_type", "targeted_hh", "redeeming_hh", "hh_redemption_rate_pct"]].to_dict("records"),
 "camp_bottom": camp.tail(3)[["CAMPAIGN", "campaign_type", "targeted_hh", "redeeming_hh", "hh_redemption_rate_pct"]].to_dict("records"),
 "redeeming_hh": int(ct.redeeming_households), "targeted_hh": int(ct.targeted_households), "txn_coupon_lines": int(ct.txn_lines_with_coupon_disc),
 "distinct_redemptions": int(ct.distinct_redemptions),
 "rs": {g: {c: float(rs.loc[g, c]) for c in rs.columns} for g in rs.index},
 # RFM
 "seg": {s: {c: float(seg.loc[s, c]) for c in seg.columns} for s in seg.index},
 "demo": {s: {c: (demo.loc[s, c] if isinstance(demo.loc[s, c], str) else float(demo.loc[s, c])) for c in demo.columns} for s in demo.index},
 # forecast
 "fc": {m: {c: float(fx.loc[m, c]) for c in ["MAE", "MAPE_pct", "bias_pct"]} for m in fx.index}, "fc_best": best,
 "fc_roll": acc[acc["mode"] == "rolling 1-step"].set_index("method")[["MAE", "MAPE_pct"]].to_dict("index"),
 "fc_fwd": float(fwd.forecast.iloc[0]),
 "promo_share_in_scope": round((scope.loc[["Mailer only","Display only","Display + Mailer"],"pct_sales"].sum()) / (100 - scope.loc["Unknown (no causal data)","pct_sales"]) * 100, 2),
 "y1_spend_per_hh_wk": round(y1.avg_weekly_sales / y1.avg_weekly_active_hh, 2), "y2_spend_per_hh_wk": round(y2.avg_weekly_sales / y2.avg_weekly_active_hh, 2),
}
h = R("r_forecast_holdout"); hb = h[(h["mode"] == "fixed origin (wk 89)") & (h.method == best)].copy()
hb["abs_err"] = (hb.actual - hb.forecast).abs(); mx = hb.loc[hb.abs_err.idxmax()]
f.update({"fc_max_week": int(mx.WEEK_NO), "fc_max_actual": float(mx.actual), "fc_max_fc": float(mx.forecast),
          "spend_hh_growth_pct": round((f["y2_spend_per_hh_wk"] / f["y1_spend_per_hh_wk"] - 1) * 100, 2)})
json.dump(f, open(f"{res}/report_facts.json", "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print(json.dumps({x: f[x] for x in ["raw_txn_rows", "fuel_units", "causal_cov_pct", "y2_growth_pct", "hh_growth_pct", "top3_dept_pct",
      "pl_units_share", "top10_share", "retention_avg", "fc_best", "fc_fwd", "kiosk_gas_pct"]}, indent=1, default=str))
