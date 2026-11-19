"""Charts for the report. Usage: python3 05_charts.py <results_dir> <charts_dir>
Every chart reads a CSV produced by the SQL files or 04_forecast.py - no numbers are typed in."""
import sys, os, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

res, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
# Black, white and grey only
BLUE, ORANGE, GRAY, INK, INK2 = "#3a3a3a", "#b0b0b0", "#cccccc", "#000000", "#4d4d4d"
plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 10, "axes.edgecolor": GRAY,
    "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.8,
    "axes.axisbelow": True, "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left"})
money_k = FuncFormatter(lambda v, _: f"${v/1000:,.0f}K")
money_m = FuncFormatter(lambda v, _: f"${v/1e6:,.1f}M")

def save(fig, name):
    fig.tight_layout(); fig.savefig(f"{out}/{name}.png", dpi=180); plt.close(fig)

# 1 Weekly sales trend
w = pd.read_csv(f"{res}/r_weekly.csv")
fig, ax = plt.subplots(figsize=(8, 3.4))
ax.axvspan(0.5, 16.5, color="#f0f0f0", zorder=0)
ax.text(8.5, w.sales.max()*1.02, "Ramp-up\n(households joining)", ha="center", va="top", color=INK2, fontsize=8.5)
ax.plot(w.WEEK_NO, w.sales, color=BLUE, lw=2)
ax.yaxis.set_major_formatter(money_k); ax.set_xlabel("Week number"); ax.set_xlim(1, 102)
ax.set_title("Weekly sales, weeks 1-102"); save(fig, "01_weekly_sales")

# 2 Department sales (merchandise, top 10)
d = pd.read_csv(f"{res}/r_department.csv"); dm = d[d.is_merch == 1].head(10).iloc[::-1]
fig, ax = plt.subplots(figsize=(8, 3.6))
b = ax.barh(dm.DEPARTMENT, dm.sales, color=BLUE, height=0.65)
for rect, pct in zip(b, dm.pct_merch_sales):
    ax.text(rect.get_width(), rect.get_y()+rect.get_height()/2, f"  {pct:.1f}%", va="center", fontsize=8.5, color=INK2)
ax.xaxis.set_major_formatter(money_m); ax.grid(axis="y", visible=False)
ax.set_title("Top 10 merchandise departments by sales (label = % of merchandise sales)"); save(fig, "02_department_sales")

# 3 Top commodities
c = pd.read_csv(f"{res}/r_commodity_top10.csv").iloc[::-1]
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.barh(c.COMMODITY_DESC.str.title(), c.sales, color=BLUE, height=0.65)
ax.xaxis.set_major_formatter(money_k); ax.grid(axis="y", visible=False)
ax.set_title("Top 10 commodities by sales"); save(fig, "03_top_commodities")

# 4 Promotion lift: units vs sales value
p = pd.read_csv(f"{res}/r_promo_lift.csv").set_index("promo_status").loc[["Display only", "Mailer only", "Display + Mailer"]]
fig, ax = plt.subplots(figsize=(8, 3.4)); x = range(len(p)); bw = 0.36
b1 = ax.bar([i-bw/2 for i in x], p.unit_lift_pct, bw, color=BLUE, label="Unit lift %")
b2 = ax.bar([i+bw/2 for i in x], p.sales_lift_pct, bw, color=ORANGE, edgecolor=INK, linewidth=0.6, label="Sales value lift %")
for bars in (b1, b2):
    for r in bars:
        v = r.get_height(); ax.text(r.get_x()+r.get_width()/2, v + (0.6 if v >= 0 else -0.6), f"{v:+.1f}%",
                                    ha="center", va="bottom" if v >= 0 else "top", fontsize=8.5, color=INK)
ax.axhline(0, color=INK2, lw=0.8); ax.set_xticks(list(x)); ax.set_xticklabels(p.index)
ax.set_ylabel("Change vs non-promoted weeks"); ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.set_ylim(min(p.sales_lift_pct.min(), 0)-5, p.unit_lift_pct.max()+5); ax.legend(frameon=False, loc="upper left")
ax.set_title("Promoted weeks: more units, lower sales value (matched product-store pairs)"); save(fig, "04_promo_lift")

# 5 RFM segments: share of households vs share of sales
s = pd.read_csv(f"{res}/r_rfm_segment.csv"); s["label"] = s.segment.str[2:]
fig, ax = plt.subplots(figsize=(8, 3.4)); x = range(len(s)); bw = 0.36
b1 = ax.bar([i-bw/2 for i in x], s.pct_households, bw, color=GRAY, edgecolor=INK, linewidth=0.6, label="% of households")
b2 = ax.bar([i+bw/2 for i in x], s.pct_sales, bw, color=BLUE, label="% of sales")
for bars in (b1, b2):
    for r in bars: ax.text(r.get_x()+r.get_width()/2, r.get_height()+0.6, f"{r.get_height():.1f}", ha="center", fontsize=8, color=INK)
ax.set_xticks(list(x)); ax.set_xticklabels(s.label); ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.legend(frameon=False); ax.set_title("RFM segments: share of households vs share of sales"); save(fig, "05_rfm_segments")

# 6 Forecast holdout
h = pd.read_csv(f"{res}/r_forecast_holdout.csv"); acc = pd.read_csv(f"{res}/r_forecast_accuracy.csv")
best = acc[acc["mode"] == "fixed origin (wk 89)"].iloc[0]
hb = h[(h["mode"] == "fixed origin (wk 89)") & (h.method == best.method)]
sn = h[(h["mode"] == "fixed origin (wk 89)") & (h.method == "Seasonal naive (t-52)")]
tail = w[(w.WEEK_NO >= 70) & (w.WEEK_NO <= 101)]
fig, ax = plt.subplots(figsize=(8, 3.4))
ax.axvspan(89.5, 101.5, color="#f0f0f0", zorder=0)
ax.plot(tail.WEEK_NO, tail.sales, color=INK, lw=2, label="Actual")
ax.plot(hb.WEEK_NO, hb.forecast, color=INK2, lw=2, ls="--", label=f"{best.method} (MAPE {best.MAPE_pct:.1f}%)")
ax.plot(sn.WEEK_NO, sn.forecast, color="#8c8c8c", lw=1.8, ls=":",
        label=f"Seasonal naive t-52 (MAPE {acc[(acc['mode']=='fixed origin (wk 89)') & (acc.method=='Seasonal naive (t-52)')].MAPE_pct.iloc[0]:.1f}%)")
ax.text(95.5, tail.sales.min()*0.94, "Holdout", ha="center", va="bottom", fontsize=8.5, color=INK2)
ax.yaxis.set_major_formatter(money_k); ax.set_xlabel("Week number"); ax.set_ylim(tail.sales.min()*0.93, tail.sales.max()*1.06)
ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=3)
ax.set_title("Baseline forecast vs actual, holdout weeks 90-101"); save(fig, "06_forecast_holdout")

# 7 Campaign type redemption
ct = pd.read_csv(f"{res}/r_campaign_type.csv")
fig, ax = plt.subplots(figsize=(8, 2.8))
b = ax.bar(ct.campaign_type, ct.hh_redemption_rate_pct, color=BLUE, width=0.5)
for r in b: ax.text(r.get_x()+r.get_width()/2, r.get_height()+0.3, f"{r.get_height():.1f}%", ha="center", fontsize=9)
from matplotlib.ticker import MultipleLocator
ax.yaxis.set_major_locator(MultipleLocator(5)); ax.set_ylim(0, ct.hh_redemption_rate_pct.max()*1.2)
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%")); ax.set_ylabel("Targeted households redeeming")
ax.set_title("Coupon redemption rate by campaign type"); save(fig, "07_campaign_redemption")
print(sorted(os.listdir(out)))
