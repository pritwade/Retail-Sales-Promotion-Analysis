"""Verify every number printed in the report PDF exists in a computed output (results CSVs, facts JSON,
clean reconciliation/log). Usage: python3 10_verify_report_numbers.py <report.pdf> <results_dir> <clean_dir>"""
import sys, re, json, glob, subprocess, math, pandas as pd
pdf, res, clean = sys.argv[1:4]
text = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout
pool = set()
def add(v):
    try: x = float(v)
    except (TypeError, ValueError): return
    if math.isnan(x): return
    for d in (0, 1, 2): pool.add(round(abs(x), d))
    if abs(x) < 1: [pool.add(round(abs(x) * 100, d)) for d in (0, 1, 2)]
def walk(o):
    if isinstance(o, dict): [walk(v) for v in o.values()]
    elif isinstance(o, list): [walk(v) for v in o]
    else: add(o)
walk(json.load(open(f"{res}/report_facts.json")))
for f in glob.glob(f"{res}/*.csv") + glob.glob(f"{clean}/cleaning_log.csv") + glob.glob(f"{clean}/reconciliation.csv"):
    for v in pd.read_csv(f).select_dtypes("number").values.ravel(): add(v)
# numbers that are structural, not results (week ranges, section numbers, thresholds stated as method)
structural = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 16, 17, 24, 26, 49, 52, 76, 89, 90, 92, 100, 101, 102, 500, 711, 1300, 10000, 80, 2500}
bad = []
for m in re.finditer(r"(?<![\w.])\$?(-?\+?[\d,]+(?:\.\d+)?)(%?)", text):
    raw = m.group(1).replace(",", "").replace("+", "").replace("-", "")
    if not raw or raw == ".": continue
    x = float(raw); d = len(raw.split(".")[1]) if "." in raw else 0
    if x in structural: continue
    if round(x, d) not in pool: bad.append(m.group(0))
print("numbers checked:", len(re.findall(r"\d", text)) and len(list(re.finditer(r"(?<![\w.])\$?(-?\+?[\d,]+(?:\.\d+)?)(%?)", text))))
print("not found in computed outputs:", sorted(set(bad)))
