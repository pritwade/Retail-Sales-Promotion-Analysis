"""Step 9 - Excel workbook: KPI sheet, department x week pivot (SUMIFS formulas), XLOOKUP reconciliation.
Usage: python3 07_excel.py <results_dir> <out_xlsx>
Data_DeptWeek holds r_dept_week (SQL output) as values. Every summary cell is a formula on that sheet.
SQL_Results holds totals from DIFFERENT SQL tables (r_kpi_overview, r_department, r_weekly) so the
reconciliation is an independent check, not a sheet checking itself."""
import sys, pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.formatting.rule import CellIsRule
from openpyxl.workbook.properties import CalcProperties

res, out = sys.argv[1], sys.argv[2]
dw = pd.read_csv(f"{res}/r_dept_week.csv")
dept = pd.read_csv(f"{res}/r_department.csv")
wk = pd.read_csv(f"{res}/r_weekly.csv")
kpi = pd.read_csv(f"{res}/r_kpi_overview.csv").iloc[0]
kdef = pd.read_csv(f"{res}/KPI_definitions.csv")

F = "Arial"; HDR = PatternFill("solid", fgColor="D9D9D9"); SUB = PatternFill("solid", fgColor="EDEDED")
hfont = Font(name=F, bold=True, color="000000"); bfont = Font(name=F); bold = Font(name=F, bold=True)
thin = Border(bottom=Side(style="thin", color="BFBFBF"))
MONEY, INT = '$#,##0.00;($#,##0.00);"-"', '#,##0;(#,##0);"-"'

def header(ws, row, values, widths=None):
    for j, v in enumerate(values, 1):
        c = ws.cell(row=row, column=j, value=v); c.font = hfont; c.fill = HDR
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    if widths:
        for j, w in enumerate(widths, 1): ws.column_dimensions[L(j)].width = w

wb = Workbook()
# ---------------- README ----------------
ws = wb.active; ws.title = "README"
lines = [
 ("Retail Sales, Promotion & Customer Performance - Excel checks", bold),
 ("Source: dunnhumby 'The Complete Journey'. Cleaned in DuckDB (python/02_clean.py); aggregates from sql/02_weekly_trend.sql.", bfont),
 ("", bfont),
 ("Sheets", bold),
 ("KPI_Definitions - formula, definition, assumptions and value of every KPI (values from SQL output).", bfont),
 ("Data_DeptWeek - department x week sales, merchandise units and baskets (SQL output table r_dept_week, pasted as values).", bfont),
 ("Pivot_Dept_Week - pivot-style summary: departments in rows, weeks in columns. Every cell is a SUMIFS formula on Data_DeptWeek.", bfont),
 ("Dept_Summary - department totals, share of sales and units, built with SUMIFS on Data_DeptWeek.", bfont),
 ("SQL_Results - totals produced by OTHER SQL tables (r_kpi_overview, r_department, r_weekly), pasted as values.", bfont),
 ("Reconciliation - Excel totals vs SQL totals. SQL value is fetched with XLOOKUP (and an INDEX/MATCH twin for older Excel).", bfont),
 ("", bfont),
 ("Notes", bold),
 ("XLOOKUP needs Excel 2021 or Microsoft 365. The INDEX/MATCH columns give the same check in any version.", bfont),
 ("Tolerance: a row passes if |Excel - SQL| < 0.01.", bfont),
 ("Units = merchandise units only (fuel/misc QUANTITY is not an item count; see KPI_Definitions).", bfont),
 ("Light grey cells on Data_DeptWeek and SQL_Results are pasted SQL output (inputs). All other numbers are formulas. A failed check shows CHECK on a dark grey fill.", bfont),
]
for i, (t, f) in enumerate(lines, 1):
    ws.cell(row=i, column=1, value=t).font = f
ws.column_dimensions["A"].width = 130

# ---------------- KPI_Definitions ----------------
ws = wb.create_sheet("KPI_Definitions")
header(ws, 1, list(kdef.columns), [30, 55, 50, 70, 40, 32])
for i, r in enumerate(kdef.itertuples(index=False), 2):
    for j, v in enumerate(r, 1):
        c = ws.cell(row=i, column=j, value=v); c.font = bfont; c.alignment = Alignment(wrap_text=True, vertical="top")
ws.freeze_panes = "B2"

# ---------------- Data_DeptWeek ----------------
ws = wb.create_sheet("Data_DeptWeek")
cols = ["DEPARTMENT", "WEEK_NO", "is_merch", "sales", "merch_units", "baskets"]
header(ws, 1, cols, [22, 10, 10, 14, 14, 12])
INFILL = PatternFill("solid", fgColor="F7F7F7")
for i, r in enumerate(dw[cols].itertuples(index=False), 2):
    for j, v in enumerate(r, 1):
        c = ws.cell(row=i, column=j, value=(v.item() if hasattr(v, "item") else v)); c.font = bfont; c.fill = INFILL
        if j == 4: c.number_format = MONEY
        if j in (5, 6): c.number_format = INT
n = len(dw) + 1
ws.freeze_panes = "A2"; ws.auto_filter.ref = f"A1:F{n}"
D = f"Data_DeptWeek!$A$2:$A${n}"; W = f"Data_DeptWeek!$B$2:$B${n}"; S = f"Data_DeptWeek!$D$2:$D${n}"
U = f"Data_DeptWeek!$E$2:$E${n}"; M = f"Data_DeptWeek!$C$2:$C${n}"

# ---------------- Pivot_Dept_Week ----------------
ws = wb.create_sheet("Pivot_Dept_Week")
depts = dept.sort_values("sales", ascending=False).DEPARTMENT.tolist()
weeks = list(range(1, 103))
ws["A1"] = "Sales by department and week (SUMIFS on Data_DeptWeek)"; ws["A1"].font = Font(name=F, bold=True, size=12)
header(ws, 3, ["DEPARTMENT"] + [f"Wk {w}" for w in weeks] + ["Total"])
ws.column_dimensions["A"].width = 22
for j in range(2, len(weeks) + 3): ws.column_dimensions[L(j)].width = 11
# week numbers as numbers in hidden helper row 2 so formulas reference a cell, not a typed constant
ws.cell(row=2, column=1, value="week no. ->").font = Font(name=F, italic=True, color="808080")
for j, w in enumerate(weeks, 2):
    c = ws.cell(row=2, column=j, value=w); c.font = Font(name=F, color="808080")
first, last = 4, 3 + len(depts)
for i, d in enumerate(depts, first):
    ws.cell(row=i, column=1, value=d).font = bfont
    for j in range(2, len(weeks) + 2):
        c = ws.cell(row=i, column=j, value=f"=SUMIFS({S},{D},$A{i},{W},{L(j)}$2)"); c.number_format = MONEY; c.font = bfont
    c = ws.cell(row=i, column=len(weeks) + 2, value=f"=SUM(B{i}:{L(len(weeks)+1)}{i})"); c.number_format = MONEY; c.font = bold
tr = last + 1
ws.cell(row=tr, column=1, value="Total").font = bold
for j in range(2, len(weeks) + 3):
    c = ws.cell(row=tr, column=j, value=f"=SUM({L(j)}{first}:{L(j)}{last})"); c.number_format = MONEY; c.font = bold; c.fill = SUB
ws.freeze_panes = "B4"
PIVOT_TOTAL = f"Pivot_Dept_Week!${L(len(weeks)+2)}${tr}"

# ---------------- Dept_Summary ----------------
ws = wb.create_sheet("Dept_Summary")
header(ws, 1, ["DEPARTMENT", "Merchandise? (1=yes)", "Sales", "% of total sales", "Merchandise units", "% of merch units"], [22, 14, 16, 14, 16, 14])
last_ds = 1 + len(depts)
for i, d in enumerate(depts, 2):
    ws.cell(row=i, column=1, value=d).font = bfont
    ws.cell(row=i, column=2, value=f"=MAXIFS({M},{D},A{i})".replace("MAXIFS", "_xlfn.MAXIFS")).font = bfont
    c = ws.cell(row=i, column=3, value=f"=SUMIFS({S},{D},A{i})"); c.number_format = MONEY
    c = ws.cell(row=i, column=4, value=f"=IF($C${last_ds+1}=0,0,C{i}/$C${last_ds+1})"); c.number_format = "0.00%"
    c = ws.cell(row=i, column=5, value=f"=SUMIFS({U},{D},A{i})"); c.number_format = INT
    c = ws.cell(row=i, column=6, value=f"=IF($E${last_ds+1}=0,0,E{i}/$E${last_ds+1})"); c.number_format = "0.00%"
t = last_ds + 1
ws.cell(row=t, column=1, value="Total").font = bold
for col, fmt in [(3, MONEY), (4, "0.00%"), (5, INT), (6, "0.00%")]:
    c = ws.cell(row=t, column=col, value=f"=SUM({L(col)}2:{L(col)}{last_ds})"); c.number_format = fmt; c.font = bold; c.fill = SUB
ws.cell(row=t+1, column=1, value="Merchandise sales").font = bold
c = ws.cell(row=t+1, column=3, value=f"=SUMIFS(C2:C{last_ds},B2:B{last_ds},1)"); c.number_format = MONEY; c.font = bold
ws.freeze_panes = "A2"
DS_TOTAL_SALES, DS_MERCH_SALES, DS_TOTAL_UNITS = f"Dept_Summary!$C${t}", f"Dept_Summary!$C${t+1}", f"Dept_Summary!$E${t}"

# ---------------- SQL_Results ----------------
ws = wb.create_sheet("SQL_Results")
header(ws, 1, ["Key", "SQL value", "Source SQL table.column"], [34, 18, 40])
sql_rows = [("TOTAL|sales", kpi.total_sales, "r_kpi_overview.total_sales"),
            ("MERCH|sales", kpi.merch_sales, "r_kpi_overview.merch_sales"),
            ("MERCH|units", kpi.merch_units, "r_kpi_overview.merch_units")]
sql_rows += [(f"DEPT|{r.DEPARTMENT}|sales", r.sales, "r_department.sales") for r in dept.itertuples()]
sql_rows += [(f"DEPT|{r.DEPARTMENT}|units", r.units, "r_department.units") for r in dept.itertuples()]
sql_rows += [(f"WEEK|{r.WEEK_NO}|sales", r.sales, "r_weekly.sales") for r in wk.itertuples()]
for i, (k_, v, s_) in enumerate(sql_rows, 2):
    ws.cell(row=i, column=1, value=k_).font = bfont
    c = ws.cell(row=i, column=2, value=float(v)); c.font = bfont; c.fill = INFILL
    c.number_format = INT if k_.endswith("units") else MONEY
    ws.cell(row=i, column=3, value=s_).font = bfont
ns = len(sql_rows) + 1
SK, SV = f"SQL_Results!$A$2:$A${ns}", f"SQL_Results!$B$2:$B${ns}"
ws.freeze_panes = "A2"

# ---------------- Reconciliation ----------------
ws = wb.create_sheet("Reconciliation")
ws["A1"] = "Reconciliation: Excel (SUMIFS on Data_DeptWeek) vs SQL (separate result tables)"; ws["A1"].font = Font(name=F, bold=True, size=12)
ws["A2"] = "Rows checked"; ws["A3"] = "Rows passing (INDEX/MATCH)"; ws["A4"] = "Rows passing (XLOOKUP)"
for a in ("A2", "A3", "A4"): ws[a].font = bold
HR = 6
header(ws, HR, ["Key", "Check", "Excel value", "SQL value (XLOOKUP)", "Diff (XLOOKUP)", "Status (XLOOKUP)",
                "SQL value (INDEX/MATCH)", "Diff (INDEX/MATCH)", "Status (INDEX/MATCH)"], [34, 46, 17, 19, 15, 15, 19, 15, 17])
checks = [("TOTAL|sales", "Total sales: pivot grand total", f"={PIVOT_TOTAL}"),
          ("TOTAL|sales", "Total sales: Dept_Summary total", f"={DS_TOTAL_SALES}"),
          ("MERCH|sales", "Merchandise sales", f"={DS_MERCH_SALES}"),
          ("MERCH|units", "Merchandise units", f"={DS_TOTAL_UNITS}")]
for d in depts:
    checks.append((f"DEPT|{d}|sales", f"{d} sales", f"=SUMIFS({S},{D},\"{d}\")"))
for d in depts:
    checks.append((f"DEPT|{d}|units", f"{d} merchandise units", f"=SUMIFS({U},{D},\"{d}\")"))
for w in weeks:
    checks.append((f"WEEK|{w}|sales", f"Week {w} sales", f"=SUMIFS({S},{W},{w})"))
for i, (key, desc, f) in enumerate(checks, HR + 1):
    fmt = INT if key.endswith("units") else MONEY
    ws.cell(row=i, column=1, value=key).font = bfont
    ws.cell(row=i, column=2, value=desc).font = bfont
    for col, val in [(3, f), (4, f'=_xlfn.XLOOKUP(A{i},{SK},{SV},"missing")'), (5, f"=C{i}-D{i}"),
                     (6, f'=IF(ABS(E{i})<0.01,"MATCH","CHECK")'),
                     (7, f"=INDEX({SV},MATCH(A{i},{SK},0))"), (8, f"=C{i}-G{i}"),
                     (9, f'=IF(ABS(H{i})<0.01,"MATCH","CHECK")')]:
        c = ws.cell(row=i, column=col, value=val); c.font = bfont
        if col in (3, 4, 5, 7, 8): c.number_format = fmt
lr = HR + len(checks)
ws["B2"] = f"=COUNTA(A{HR+1}:A{lr})"; ws["B3"] = f'=COUNTIF(I{HR+1}:I{lr},"MATCH")'; ws["B4"] = f'=COUNTIF(F{HR+1}:F{lr},"MATCH")'
for a in ("B2", "B3", "B4"): ws[a].font = bold
check_fill = PatternFill("solid", fgColor="A6A6A6")
for colL in ("F", "I"):
    rng = f"{colL}{HR+1}:{colL}{lr}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"CHECK"'], fill=check_fill, font=Font(name=F, bold=True)))
ws.freeze_panes = f"C{HR+1}"

wb.calculation = CalcProperties(fullCalcOnLoad=True)
wb.save(out)
print("saved", out, "| reconciliation rows:", len(checks))
