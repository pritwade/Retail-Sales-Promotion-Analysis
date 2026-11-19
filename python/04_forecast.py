"""Step 8 - Baseline weekly sales forecast with a holdout test.
Usage: python3 04_forecast.py <results_dir>
Data: r_weekly.csv (from sql/02_weekly_trend.sql), total sales per week.
Training weeks 17-89 (after household ramp-up; weeks 1-16 excluded), holdout weeks 90-101 (12 full weeks).
Week 102 is partial (6 days) and is excluded.
Two evaluation modes:
  fixed   - forecast made once at week 89 for all 12 holdout weeks (realistic planning view)
  rolling - one-step-ahead: each week forecast from the actuals up to the week before
Methods: naive (last week), moving averages 4/8/13 weeks, seasonal naive (same week last year, t-52).
Errors: MAE ($) and MAPE (%)."""
import sys, pandas as pd, numpy as np

res = sys.argv[1]
w = pd.read_csv(f"{res}/r_weekly.csv").set_index("WEEK_NO")["sales"]
TRAIN_END, H0, H1 = 89, 90, 101
hold = w.loc[H0:H1]

def fixed(method):
    hist = w.loc[17:TRAIN_END]
    if method == "Naive (last week)":    return pd.Series(hist.iloc[-1], index=hold.index)
    if method.startswith("Moving avg"):
        k = int(method.split()[2]); return pd.Series(hist.iloc[-k:].mean(), index=hold.index)
    if method == "Seasonal naive (t-52)": return pd.Series([w.loc[t-52] for t in hold.index], index=hold.index)

def rolling(method):
    out = {}
    for t in hold.index:
        hist = w.loc[17:t-1]
        if method == "Naive (last week)": out[t] = hist.iloc[-1]
        elif method.startswith("Moving avg"): k = int(method.split()[2]); out[t] = hist.iloc[-k:].mean()
        elif method == "Seasonal naive (t-52)": out[t] = w.loc[t-52]
    return pd.Series(out)

methods = ["Naive (last week)", "Moving avg 4", "Moving avg 8", "Moving avg 13", "Seasonal naive (t-52)"]
rows, preds = [], []
for mode, fn in [("fixed origin (wk 89)", fixed), ("rolling 1-step", rolling)]:
    for m in methods:
        f = fn(m); err = hold - f
        rows.append({"mode": mode, "method": m, "MAE": round(err.abs().mean(), 2),
                     "MAPE_pct": round((err.abs() / hold).mean() * 100, 2),
                     "bias_pct": round((f.sum() / hold.sum() - 1) * 100, 2)})
        for t in hold.index:
            preds.append({"mode": mode, "method": m, "WEEK_NO": t, "actual": hold[t], "forecast": round(f[t], 2)})
acc = pd.DataFrame(rows).sort_values(["mode", "MAPE_pct"])
acc.to_csv(f"{res}/r_forecast_accuracy.csv", index=False)
pd.DataFrame(preds).to_csv(f"{res}/r_forecast_holdout.csv", index=False)

# Forward baseline: best fixed-origin method refit on weeks 17-101, next 8 weeks (103-110)
best = acc[acc["mode"] == "fixed origin (wk 89)"].iloc[0]["method"]
hist = w.loc[17:101]
if best.startswith("Moving avg"):
    k = int(best.split()[2]); fwd = {t: hist.iloc[-k:].mean() for t in range(103, 111)}
elif best == "Seasonal naive (t-52)":
    fwd = {t: w.loc[t-52] for t in range(103, 111)}
else:
    fwd = {t: hist.iloc[-1] for t in range(103, 111)}
pd.DataFrame({"WEEK_NO": list(fwd), "forecast": [round(v, 2) for v in fwd.values()], "method": best}).to_csv(
    f"{res}/r_forecast_forward.csv", index=False)
print(acc.to_string(index=False)); print("\nbest fixed-origin method:", best)
print("holdout actual total:", round(hold.sum(), 2), "| weeks", H0, "-", H1)
