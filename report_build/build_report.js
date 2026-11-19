// Builds the Word report from output/results/report_facts.json and output/charts/*.png.
// Usage: node build_report.js <facts.json> <charts_dir> <out.docx>
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, AlignmentType,
  HeadingLevel, LevelFormat, WidthType, ShadingType, BorderStyle, Footer, PageNumber, TabStopType,
} = require("docx");

const [factsPath, chartDir, outPath] = process.argv.slice(2);
const F = JSON.parse(fs.readFileSync(factsPath, "utf8"));

// ---------- formatting helpers (numbers come only from F) ----------
const chk = (v) => { if (v === undefined || v === null || !Number.isFinite(Number(v))) throw new Error("Missing number in report: " + v); return Number(v); };
const money = (v, d = 0) => "$" + chk(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const num = (v, d = 0) => chk(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (v, d = 1) => `${chk(v).toFixed(d)}%`;
const spct = (v, d = 1) => `${chk(v) >= 0 ? "+" : ""}${Number(v).toFixed(d)}%`;
const title = (s) => s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());

const FONT = "Arial", INK = "000000", MUTED = "595959", ACCENT = "000000";
const P = (children, opts = {}) => new Paragraph({ spacing: { after: 100, line: 264 }, ...opts,
  children: (Array.isArray(children) ? children : [children]).map((c) => (typeof c === "string" ? new TextRun(c) : c)) });
const B = (t) => new TextRun({ text: t, bold: true });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const bullet = (children) => new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 60, line: 252 },
  children: (Array.isArray(children) ? children : [children]).map((c) => (typeof c === "string" ? new TextRun(c) : c)) });
const caption = (t) => new Paragraph({ spacing: { before: 40, after: 160 }, children: [new TextRun({ text: t, italics: true, size: 17, color: MUTED })] });
const chart = (file, wIn, hIn) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60, after: 0 }, keepNext: true,
  children: [new ImageRun({ type: "png", data: fs.readFileSync(`${chartDir}/${file}`),
    transformation: { width: Math.round(wIn * 96), height: Math.round(hIn * 96) },
    altText: { title: file, description: file.replace(/_/g, " "), name: file } })] });

const CONTENT_W = 9360; // 6.5in at 1in margins
const cellBorder = { style: BorderStyle.SINGLE, size: 4, color: "808080" };
const borders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
function table(headers, rows, widths, opts = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const mk = (text, i, head) => new TableCell({
    borders, width: { size: widths[i], type: WidthType.DXA },
    shading: head ? { fill: "D9D9D9", type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: [new Paragraph({ alignment: !head && (opts.rightCols || []).includes(i) ? AlignmentType.RIGHT : AlignmentType.LEFT,
      children: [new TextRun({ text: String(text), bold: head, color: INK, size: 17 })] })],
  });
  return new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => mk(h, i, true)) }),
           ...rows.map((r) => new TableRow({ cantSplit: true, children: r.map((c, i) => mk(c, i, false)) }))] });
}
const spacer = () => new Paragraph({ spacing: { after: 120 }, children: [] });

// ---------- derived values ----------
const L = F.lift, D = F.disc, S = F.seg, CT = F.ctype;
const champ = S["1 Champions"], loyal = S["2 Loyal"], risk = S["4 At Risk"], lapsed = S["6 Lapsed / Low"];
const fcBest = F.fc[F.fc_best], fcSN = F.fc["Seasonal naive (t-52)"];
const dep = Object.fromEntries(F.dept.map((d) => [d.DEPARTMENT, d]));
const promoShare = F.promo_share_in_scope;

// ---------- content ----------
const body = [];
body.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "Retail Sales, Promotion & Customer Performance Analysis", bold: true, size: 36, color: ACCENT })] }));
body.push(new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: "dunnhumby “The Complete Journey”: 2,500 households, 102 weeks of grocery transactions", size: 21, color: MUTED })] }));
body.push(new Paragraph({ spacing: { after: 200 }, border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: ACCENT, space: 4 } },
  children: [new TextRun({ text: "Prit Wade  |  Portfolio project  |  Tools: DuckDB SQL, Python (pandas), Excel, Power BI", size: 18, color: MUTED })] }));

// Summary box
body.push(H2("Summary"));
[
  [B("Sales: "), `${money(F.k_total_sales, 2)} across ${num(F.k_baskets)} baskets from ${num(F.k_households)} households (average basket ${money(F.k_basket_value ?? F.k_avg_basket_value, 2)}). Grocery, Drug GM and Produce make up ${pct(F.top3_dept_pct)} of merchandise sales.`],
  [B("Promotions move volume, not value: "), `matched product-store weeks on display + mailer sold ${spct(L["Display + Mailer"].unit_lift_pct)} more units but ${spct(L["Display + Mailer"].sales_lift_pct)} sales value, because the discount depth on those weeks was ${pct(D["Display + Mailer"].retail_disc_depth_pct)} vs ${pct(D["No promotion"].retail_disc_depth_pct)} without promotion.`],
  [B("Customers are concentrated: "), `the Champions segment is ${pct(champ.pct_households)} of households and ${pct(champ.pct_sales)} of sales. "At Risk" households (${num(risk.households)}) still hold ${pct(risk.pct_sales)} of sales.`],
  [B("Data reliability: "), `promotion flags cover ${F.n_causal_stores} of ${F.n_stores} stores and match ${pct(F.causal_cov_pct)} of sales; demographics exist for ${F.n_demo} of 2,500 households; ${pct(F.fuel_units / F.raw_units * 100)} of raw units are fuel/misc meter readings, not items.`],
].forEach((b) => body.push(bullet(b)));

// 1 Objective
body.push(H1("1. Objective"));
body.push(P("Answer one business question for a grocery retailer: which categories, promotions and customer segments drive sales, and where is the data unreliable? The output is meant to support merchandising, promotion planning and customer marketing decisions, with every figure traceable to a query."));

// 2 Data & method
body.push(H1("2. Data and method"));
body.push(P(`Eight files were profiled before any analysis: transactions (${num(F.raw_txn_rows)} lines), products (${num(F.n_products)}), household demographics (${F.n_demo}), campaigns (${F.n_campaigns}), campaign targeting (${num(F.n_campaign_table)}), coupons (${num(F.n_coupon_rows)}), redemptions (${num(F.n_redemptions)}) and causal display/mailer flags (${num(F.raw_causal_rows)} rows). The causal file was loaded in full into DuckDB, which streams the CSV in chunks, so no sampling was needed.`));
body.push(P(`Pipeline: Python profiling → documented cleaning rules → SQL analysis (CTEs and window functions: LAG for week-over-week change, RANK within department, NTILE for RFM scores, running totals) → Python forecast and charts → Excel reconciliation → Power BI star schema. The data has no calendar dates, only day 1–711 and week 1–102, so seasonality is described by week number.`));
body.push(P([B("Like-for-like comparison. "), `Weeks 1–16 are a ramp-up period while households join the panel (average ${num(F.ramp_avg_hh, 0)} active households a week vs about 1,300 later). Growth is therefore measured on two matched 26-week windows: weeks 24–49 vs weeks 76–101.`]));

// 3 Data quality
body.push(H1("3. Data quality findings"));
body.push(P(`Cleaning removed only lines with no quantity, no sales and no discount (${num(F.t1_removed)} rows). Everything else unusual was flagged and kept. Sales reconcile exactly to the raw file: ${money(F.raw_sales, 2)} before and after (difference ${money(F.sales_diff, 2)}); units and all three discount columns also reconcile to zero difference.`));
body.push(table(["Issue", "Size", "Treatment"], [
  ["Fuel / misc lines: QUANTITY is a meter reading", `${num(F.fuel_rows)} rows; ${num(F.fuel_units)} of ${num(F.raw_units)} units`, "Flagged non-merchandise; excluded from units"],
  ["Lines with qty 0 and sales 0 but a coupon discount", `${num(F.t1b_rows)} rows; ${money(F.t1b_coupon, 2)} coupon`, "Kept (deleting would understate coupons)"],
  ["Empty lines (no qty, sales or discount)", `${num(F.t1_removed)} rows`, "Removed"],
  ["Households without demographics", `${num(F.nodemo_hh)} of 2,500; ${money(F.nodemo_sales, 0)} sales`, "Kept; demographic views labelled"],
  ["Promo flags: limited stores and weeks", `${F.n_causal_stores} of ${F.n_stores} stores; weeks 9–101`, "Promo analysis limited to that scope"],
  ["Causal keys with conflicting duplicate rows", `${num(F.causal_dup_keys)} keys`, "Collapsed; promoted if either row flagged"],
  ["Duplicate coupon rows", `${num(F.coupon_dups)} rows`, "Removed"],
  ["Same redemption credited to 2 campaigns", `${F.multi_campaign_redemptions} rows`, "Flagged; distinct count used for totals"],
  ["No returns recorded (no negative rows)", "0 rows", "Returns cannot be measured"],
  ["'Single' households with size ≥ 2", `${F.single_inconsistent} households`, "Flagged, not corrected"],
], [3900, 2900, 2560]));
body.push(spacer());

// 4 KPI definitions
body.push(H1("4. KPI definitions"));
body.push(table(["KPI", "Formula", "Value"], [
  ["Sales", "SUM(SALES_VALUE), net of retail discount", money(F.k_total_sales, 2)],
  ["Merchandise sales", "Sales excluding fuel, misc and store-coupon departments", money(F.k_merch_sales, 2)],
  ["Units", "SUM(QUANTITY), merchandise lines only", num(F.k_merch_units)],
  ["Baskets / basket value", "COUNT(DISTINCT BASKET_ID); Sales ÷ Baskets", `${num(F.k_baskets)} / ${money(F.k_avg_basket_value, 2)}`],
  ["Sales per household", "Sales ÷ distinct households", money(F.k_sales_per_household, 2)],
  ["Commodity repeat rate", "Buyers in ≥ 2 weeks ÷ all buyers (median, ≥ 500 buyers)", `${pct(F.repeat_median)} (${F.repeat_n} commodities)`],
  ["4-week retention", "Active in period p and p+1 ÷ active in p (after ramp-up)", pct(F.retention_avg, 2)],
  ["Discount depth", "−discount ÷ (sales − retail disc − coupon-match disc)", `Retail ${pct(F.k_retail_disc_depth_pct, 2)}; coupon ${pct(F.k_coupon_disc_depth_pct, 2)}; match ${pct(F.k_coupon_match_depth_pct, 2)}`],
  ["Promotion lift", "Avg weekly promoted ÷ avg weekly non-promoted, same product and store, − 1", "See section 5.3"],
], [2300, 4760, 2300], { rightCols: [2] }));
body.push(P([new TextRun({ text: "SALES_VALUE was checked against the shelf price: sales plus the retail discount equals the regular price, so sales are already net of loyalty discounts. Full definitions and assumptions are in KPI_definitions.csv and the Excel workbook.", size: 17, color: MUTED })], { spacing: { before: 80, after: 100 } }));

// 5 Findings
body.push(H1("5. Key findings"));
body.push(H2("5.1 Sales trend"));
body.push(chart("01_weekly_sales.png", 6.3, 2.68));
body.push(caption("Figure 1. Weekly sales (all lines). Source: r_weekly (sql/02_weekly_trend.sql)."));
body.push(P(`After the ramp-up, weekly sales are stable at roughly $80K–$100K. Sales in weeks 76–101 were ${money(F.y2_sales, 0)}, ${spct(F.y2_growth_pct)} vs weeks 24–49 (${money(F.y1_sales, 0)}). Two things drove it: active households per week rose ${spct(F.hh_growth_pct)} (${num(F.y1_hh, 0)} to ${num(F.y2_hh, 0)}), and weekly spend per active household rose ${spct(F.spend_hh_growth_pct)} (${money(F.y1_spend_per_hh_wk, 2)} to ${money(F.y2_spend_per_hh_wk, 2)}). Average 4-week retention after ramp-up is ${pct(F.retention_avg)}.`));

body.push(H2("5.2 Merchandising and assortment"));
body.push(chart("02_department_sales.png", 6.3, 2.84));
body.push(caption("Figure 2. Top 10 merchandise departments. Source: r_department (sql/03_department_mix.sql)."));
body.push(P(`Grocery alone is ${pct(dep.GROCERY.pct_merch_sales)} of merchandise sales. Fuel (KIOSK-GAS) is ${pct(F.kiosk_gas_pct)} of total sales and is excluded from merchandise views. The top 10 commodities make up ${pct(F.top10_share)} of merchandise sales, led by ${title(F.top10[0].COMMODITY_DESC)} (${money(F.top10[0].sales, 0)}) and ${title(F.top10[1].COMMODITY_DESC)} (${money(F.top10[1].sales, 0)}).`));
body.push(P([B("Private label "), `is ${pct(F.pl_share)} of merchandise sales and ${pct(F.pl_units_share)} of units, at ${money(F.pl_price, 2)} per unit vs ${money(F.nb_price, 2)} for national brands. Share varies widely: ${title(F.top10[2].COMMODITY_DESC)} ${pct(F.top10[2].private_label_pct)}, ${title(F.top10[3].COMMODITY_DESC)} ${pct(F.top10[3].private_label_pct)}, but Drug GM only ${pct(dep["DRUG GM"].private_label_pct)}.`]));
body.push(table(["Fastest growing (wk 76–101 vs 24–49)", "Growth", "Biggest decliners", "Growth"],
  F.growers.map((g, i) => [title(g.COMMODITY_DESC), spct(g.growth_pct), title(F.decliners[i].COMMODITY_DESC), spct(F.decliners[i].growth_pct)]),
  [3330, 1350, 3330, 1350], { rightCols: [1, 3] }));
body.push(caption("Commodities with at least $10,000 of sales in weeks 24–49. Source: r_commodity_growers / r_commodity_decliners."));
body.push(P(`${title(F.decliners[0].COMMODITY_DESC)} is the largest commodity and also the biggest decliner: ${money(F.decliners[0].sales_wk24_49, 0)} to ${money(F.decliners[0].sales_wk76_101, 0)} between the two windows, while overall sales grew.`));

body.push(H2("5.3 Promotions, pricing and coupons"));
body.push(chart("04_promo_lift.png", 6.3, 2.68));
body.push(caption("Figure 3. Matched product-store lift vs non-promoted weeks. Source: r_promo_lift (sql/06_promotions.sql)."));
body.push(P(`Within the ${F.n_causal_stores} stores with promotion flags, ${pct(promoShare)} of merchandise sales happened in promoted product-weeks. Comparing each product at the same store in promoted vs non-promoted weeks (${num(L["Mailer only"].matched_product_store_pairs)} mailer-only pairs, ${num(L["Display only"].matched_product_store_pairs)} display-only, ${num(L["Display + Mailer"].matched_product_store_pairs)} both):`));
body.push(bullet([B("Units rise "), `${spct(L["Display only"].unit_lift_pct)} (display), ${spct(L["Mailer only"].unit_lift_pct)} (mailer), ${spct(L["Display + Mailer"].unit_lift_pct)} (both). Shelf-price value rises in line (${spct(L["Display + Mailer"].gross_value_lift_pct)} for both).`]));
body.push(bullet([B("Sales value falls "), `${spct(L["Display only"].sales_lift_pct)}, ${spct(L["Mailer only"].sales_lift_pct)} and ${spct(L["Display + Mailer"].sales_lift_pct)}, because retail discount depth is ${pct(D["Mailer only"].retail_disc_depth_pct)} on mailer weeks and ${pct(D["Display + Mailer"].retail_disc_depth_pct)} on display + mailer weeks, vs ${pct(D["No promotion"].retail_disc_depth_pct)} otherwise.`]));
body.push(bullet([B("By department (any promotion), "), `unit lift is strongest in ${title(F.lift_dept[0].DEPARTMENT)} (${spct(F.lift_dept[0].unit_lift_pct)}) and ${title(F.lift_dept[1].DEPARTMENT)} (${spct(F.lift_dept[1].unit_lift_pct)}), and weakest in ${title(F.lift_dept[F.lift_dept.length - 1].DEPARTMENT)} (${spct(F.lift_dept[F.lift_dept.length - 1].unit_lift_pct)}).`]));
body.push(P([B("Coupon campaigns. "), `TypeA campaigns reached ${num(CT.TypeA.targeted_hh_slots)} household-campaign targets with a ${pct(CT.TypeA.hh_redemption_rate_pct)} household redemption rate, about twice TypeB (${pct(CT.TypeB.hh_redemption_rate_pct)}) and TypeC (${pct(CT.TypeC.hh_redemption_rate_pct)}). The best campaigns were #${F.camp_top[0].CAMPAIGN} (${pct(F.camp_top[0].hh_redemption_rate_pct)}) and #${F.camp_top[1].CAMPAIGN} (${pct(F.camp_top[1].hh_redemption_rate_pct)}). Redeeming households spent ${money(F.rs.Redeemed.avg_weekly_spend_8wk_before, 2)} a week before campaigns vs ${money(F.rs["Did not redeem"].avg_weekly_spend_8wk_before, 2)} for non-redeemers, so redeemers were already heavier shoppers.`]));
body.push(chart("07_campaign_redemption.png", 5.6, 1.96));
body.push(caption("Figure 4. Share of targeted households redeeming at least one coupon, by campaign type. Source: r_campaign_type (sql/07_campaigns.sql)."));
body.push(P([new TextRun({ text: `Caveats: lift is descriptive, not causal. Only weeks with a sale are observed, retailers pick which items to promote, and flags cover ${pct(F.causal_cov_pct)} of sales. Only ${num(F.n_redemptions)} of ${num(F.txn_coupon_lines)} coupon-discounted lines are campaign redemptions, and redemptions carry no basket ID.`, size: 17, color: MUTED })]));

body.push(H2("5.4 Customer segments (RFM)"));
body.push(chart("05_rfm_segments.png", 6.3, 2.68));
body.push(caption("Figure 5. Recency (days since last trip), frequency (baskets) and monetary (sales) scored 1–5 with NTILE. Source: r_rfm_segment (sql/08_rfm.sql)."));
body.push(table(["Segment", "Households", "% of sales", "Sales / hh", "Baskets / hh", "Median recency (days)"],
  Object.entries(S).map(([k, s]) => [k.slice(2), num(s.households), pct(s.pct_sales), money(s.avg_sales_per_hh, 0), num(s.avg_baskets, 1), num(s.median_recency_days, 0)]),
  [2160, 1300, 1300, 1500, 1500, 1600], { rightCols: [1, 2, 3, 4, 5] }));
body.push(spacer());
body.push(P(`Champions and Loyal households (${pct(champ.pct_households + loyal.pct_households)} of households) generate ${pct(champ.pct_sales + loyal.pct_sales)} of sales. At Risk households have a median ${num(risk.median_recency_days, 0)} days since their last trip but average ${money(risk.avg_sales_per_hh, 0)} each, so they are worth winning back. Demographics cover ${pct(F.demo["1 Champions"].pct_with_demo)} of Champions but only ${pct(F.demo["6 Lapsed / Low"].pct_with_demo)} of Lapsed households, so demographic profiles describe the engaged base, not all shoppers.`));

body.push(H2("5.5 Forecast baseline"));
body.push(chart("06_forecast_holdout.png", 6.3, 2.68));
body.push(caption("Figure 6. Trained on weeks 17–89, tested on weeks 90–101. Source: r_forecast_accuracy (python/04_forecast.py)."));
body.push(P(`This is a simple baseline, not a production model. Forecasting all 12 holdout weeks from week 89, the ${F.fc_best.toLowerCase()} method had the lowest error (MAPE ${pct(fcBest.MAPE_pct, 2)}, MAE ${money(fcBest.MAE, 0)}), slightly better than seasonal naive (MAPE ${pct(fcSN.MAPE_pct, 2)}). All five fixed-origin methods under-forecast the holdout (bias ${spct(fcBest.bias_pct)} for the best), and the largest miss is week ${F.fc_max_week} (actual ${money(F.fc_max_actual, 0)} vs forecast ${money(F.fc_max_fc, 0)}). The forward baseline for the next weeks is ${money(F.fc_fwd, 0)} a week.`));

// 6 Recommendations
body.push(H1("6. Recommendations"));
[
  [B("Test shallower promotional discounts. "), `Promotions lift units but reduce sales value at current depths (${pct(D["Display + Mailer"].retail_disc_depth_pct)} on display + mailer). Run store-level A/B tests with control stores before scaling, and judge promotions on margin, which this data cannot measure.`],
  [B("Focus promotions on high-response departments. "), `${title(F.lift_dept[0].DEPARTMENT)}, ${title(F.lift_dept[1].DEPARTMENT)} and ${title(F.lift_dept[2].DEPARTMENT)} showed the largest unit lift from any promotion; ${title(F.lift_dept[F.lift_dept.length - 1].DEPARTMENT)} the smallest.`],
  [B("Review the declining Soft Drinks category "), `(largest commodity, ${spct(F.decliners[0].growth_pct)}) and give space and features to growers such as ${title(F.growers[0].COMMODITY_DESC)}, ${title(F.growers[1].COMMODITY_DESC)} and ${title(F.growers[2].COMMODITY_DESC)}.`],
  [B("Explore private label in low-share departments "), `such as Drug GM (${pct(dep["DRUG GM"].private_label_pct)} private label), where national brands dominate.`],
  [B("Run a win-back programme for At Risk households "), `(${num(risk.households)} households, ${pct(risk.pct_sales)} of sales), using the TypeA campaign format, which had the highest redemption rate (${pct(CT.TypeA.hh_redemption_rate_pct)}).`],
  [B("Fix data gaps: "), `extend display/mailer flags to all stores, record returns, add basket IDs to redemptions and raise demographic coverage beyond ${F.n_demo} households.`],
].forEach((b) => body.push(bullet(b)));

// 7 Limitations
body.push(H1("7. Limitations"));
[
  "No cost, margin or inventory data. Profitability, sell-through and stock-based measures cannot be assessed.",
  "No calendar dates. Holidays and months cannot be named, only week numbers.",
  "Promotion and campaign results are associations, not causal effects. There is no random control group, and only weeks with a sale are observed.",
  `The household panel ramps up over weeks 1–16, and demographics cover ${F.n_demo} of 2,500 households.`,
  "Discount depth assumes COUPON_DISC is manufacturer-funded and that SALES_VALUE is net of retail discount (the latter verified on the data).",
].forEach((t) => body.push(bullet(t)));

body.push(H1("8. Note on AI assistance"));
body.push(P("This project was built with AI assistance (Claude, by Anthropic), used as a mentor and pair programmer for the SQL, Python and documentation. Every figure in this report comes from code run on the actual dataset. The queries, scripts and reconciliation checks are in the project files so the results can be reproduced."));

// ---------- document ----------
const doc = new Document({
  creator: "Prit Wade", title: "Retail Sales, Promotion & Customer Performance Analysis",
  styles: {
    default: { document: { run: { font: FONT, size: 20, color: INK } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true, color: ACCENT }, paragraph: { spacing: { before: 260, after: 100 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 22, bold: true, color: INK }, paragraph: { spacing: { before: 180, after: 80 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 360, hanging: 240 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1080, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }],
      children: [new TextRun({ text: "Retail Sales, Promotion & Customer Performance Analysis", size: 16, color: MUTED }),
                 new TextRun({ children: ["\tPage ", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES], size: 16, color: MUTED })] })] }) },
    children: body,
  }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(outPath, buf); console.log("wrote", outPath); });
