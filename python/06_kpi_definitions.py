"""Step 3 - KPI definitions sheet. Values are read from SQL outputs, not typed.
Usage: python3 06_kpi_definitions.py <results_dir>"""
import sys, pandas as pd
res = sys.argv[1]
k = pd.read_csv(f"{res}/r_kpi_overview.csv").iloc[0]
lift = pd.read_csv(f"{res}/r_promo_lift.csv").set_index("promo_status")
rep = pd.read_csv(f"{res}/r_commodity_repeat.csv"); ret = pd.read_csv(f"{res}/r_hh_retention.csv")
G = "SUM(SALES_VALUE) - SUM(RETAIL_DISC) - SUM(COUPON_MATCH_DISC)"
rows = [
 ("Sales", "SUM(SALES_VALUE)", "Money the retailer received for all lines (net of retail discount and coupon-match discount).",
  "Includes non-merchandise lines (fuel, misc). SALES_VALUE is already net of RETAIL_DISC (checked: sales + discount = regular shelf price).",
  f"${k.total_sales:,.2f}", "r_kpi_overview.total_sales"),
 ("Merchandise sales", "SUM(SALES_VALUE) WHERE is_merch = 1", "Sales excluding KIOSK-GAS, MISC SALES TRAN, MISC. TRANS., COUP/STR & MFG and UNKNOWN departments.",
  "Used for department, commodity and brand analysis.", f"${k.merch_sales:,.2f}", "r_kpi_overview.merch_sales"),
 ("Units", "SUM(UNITS_MERCH)  (= QUANTITY for merchandise lines, 0 otherwise)", "Items sold, merchandise only.",
  "Fuel/misc QUANTITY is not an item count (median about 10,557 per line) and would be 98.7% of raw units.", f"{k.merch_units:,.0f}", "r_kpi_overview.merch_units"),
 ("Baskets", "COUNT(DISTINCT BASKET_ID)", "Shopping trips.", "After removing 9,440 empty lines (581 baskets had only empty lines).",
  f"{k.baskets:,.0f}", "r_kpi_overview.baskets"),
 ("Basket value", "Sales / Baskets", "Average spend per trip.", "Uses total sales (incl. non-merchandise).", f"${k.avg_basket_value:,.2f}", "r_kpi_overview.avg_basket_value"),
 ("Sales per household", "Sales / COUNT(DISTINCT household_key)", "Average two-year spend per household.",
  "All 2,500 households; households joined in different weeks, so exposure differs.", f"${k.sales_per_household:,.2f}", "r_kpi_overview.sales_per_household"),
 ("Repeat purchase rate (household)", "Households with >= 2 baskets / all households", "Share of households that came back at least once.",
  "Near 100% in a loyalty panel, so not very informative on its own.", f"{k.pct_hh_2plus_baskets:.2f}%", "r_kpi_overview.pct_hh_2plus_baskets"),
 ("Repeat purchase rate (commodity)", "Households buying the commodity in >= 2 different weeks / households buying it at least once",
  "How habitual a category is.", "Merchandise, sales > 0. Median across commodities with >= 500 buyers shown.",
  f"{rep[rep.buyers>=500].repeat_rate_pct.median():.2f}% median ({(rep.buyers>=500).sum()} commodities)", "r_commodity_repeat"),
 ("4-week household retention", "Households active in period p and p+1 / households active in period p", "Return rate between consecutive 4-week periods.",
  "Full weeks 2-101 only.", f"{ret[ret.period>=5].retention_pct.mean():.2f}% average (periods 5-24, after ramp-up)", "r_hh_retention"),
 ("Retail discount depth", f"-SUM(RETAIL_DISC) / ({G})", "Retailer-funded (loyalty) discount as % of value before retailer discounts.",
  "Gross value = shelf value before retail and coupon-match discounts.", f"{k.retail_disc_depth_pct:.2f}%", "r_kpi_overview.retail_disc_depth_pct"),
 ("Coupon discount depth", f"-SUM(COUPON_DISC) / ({G})", "Manufacturer coupon discount as % of gross value.",
  "COUPON_DISC is treated as manufacturer-funded and is not subtracted from SALES_VALUE in the gross formula.", f"{k.coupon_disc_depth_pct:.2f}%", "r_kpi_overview.coupon_disc_depth_pct"),
 ("Coupon-match discount depth", f"-SUM(COUPON_MATCH_DISC) / ({G})", "Retailer match on manufacturer coupons as % of gross value.", "", f"{k.coupon_match_depth_pct:.2f}%", "r_kpi_overview.coupon_match_depth_pct"),
 ("Promotion lift (units / sales)", "SUM over matched pairs of avg weekly promoted units (or sales) / SUM of avg weekly non-promoted units (or sales) - 1",
  "Change in a product's weekly units or sales at a store when on display/mailer vs when not.",
  "Only 115 causal stores, weeks 9-101; only product-store pairs with both promoted and non-promoted weeks; only weeks with a sale are observed. Descriptive, not causal.",
  "; ".join(f"{s}: units {lift.loc[s,'unit_lift_pct']:+.1f}%, sales {lift.loc[s,'sales_lift_pct']:+.1f}%" for s in ["Display only","Mailer only","Display + Mailer"]),
  "r_promo_lift"),
 ("Coupon redemption rate", "Redeeming households / targeted households, per campaign", "Share of targeted households that redeemed at least one coupon.",
  "Redemptions have no BASKET_ID, so they cannot be tied to a specific sale.", "see r_campaign", "r_campaign"),
]
df = pd.DataFrame(rows, columns=["KPI", "Formula", "Business definition", "Assumptions", "Value", "Source table.column"])
df.to_csv(f"{res}/KPI_definitions.csv", index=False)
print(df[["KPI", "Value"]].to_string(index=False))
