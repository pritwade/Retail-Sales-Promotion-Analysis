# Power BI build guide: Retail Sales, Promotion & Customer Performance

All tables are in `powerbi_tables/`, exported by `python/08_powerbi_exports.py`. Load them with **Get Data → Text/CSV**. In Power Query, set the data types listed below. Don't let Power BI guess the types of BASKET_ID or COUPON_UPC (they are 11-digit numbers; use **Whole Number**).

## 1. Tables

| Table | Grain | Rows | Key columns |
|---|---|---|---|
| FactSales | one product line in one basket | 2,586,292 | household_key, BASKET_ID, WEEK_NO, STORE_ID, PRODUCT_ID |
| DimProduct | product | 92,353 | PRODUCT_ID |
| DimHousehold | household (RFM + demographics) | 2,500 | household_key |
| DimWeek | week 1-102 | 102 | WEEK_NO |
| DimStore | store | 582 | STORE_ID |
| DimCampaign | campaign | 30 | CAMPAIGN |
| FactCampaignTarget | household targeted by a campaign | 7,208 | household_key, CAMPAIGN |
| FactCouponRedemption | coupon redemption | 2,318 | household_key, CAMPAIGN |
| FactForecast | week × method × mode | 128 | WEEK_NO |
| PromoLiftSummary | promo type (pre-computed in SQL) | 3 | promo_status |
| DataQualityLog | cleaning rule | 19 | rule_id |

Data types: money columns (SALES_VALUE, RETAIL_DISC, COUPON_DISC, COUPON_MATCH_DISC, GROSS_VALUE, total_sales, actual, forecast) → **Fixed decimal number**. All flag columns (is_*, has_*, in_causal_scope) → **Whole Number**.

## 2. Relationships (star schema)

All relationships are **many-to-one, single direction** (dimension filters fact).

| From (many) | To (one) |
|---|---|
| FactSales[PRODUCT_ID] | DimProduct[PRODUCT_ID] |
| FactSales[household_key] | DimHousehold[household_key] |
| FactSales[WEEK_NO] | DimWeek[WEEK_NO] |
| FactSales[STORE_ID] | DimStore[STORE_ID] |
| FactCampaignTarget[household_key] | DimHousehold[household_key] |
| FactCampaignTarget[CAMPAIGN] | DimCampaign[CAMPAIGN] |
| FactCouponRedemption[household_key] | DimHousehold[household_key] |
| FactCouponRedemption[CAMPAIGN] | DimCampaign[CAMPAIGN] |
| FactForecast[WEEK_NO] | DimWeek[WEEK_NO] |

The forward-forecast weeks (103-110) are not in DimWeek. The relationship leaves them blank, which is fine: plot FactForecast[WEEK_NO] directly on the forecast page. PromoLiftSummary and DataQualityLog stay unrelated (display tables).

Mark nothing as a date table. The dataset has **no calendar dates**, only DAY 1-711 and WEEK_NO 1-102.

## 3. DAX measures

Create a blank table called `_Measures` and add these measures to it.

```DAX
Sales = SUM ( FactSales[SALES_VALUE] )

Merch Sales = CALCULATE ( [Sales], FactSales[is_merch] = 1 )

Units = SUM ( FactSales[UNITS_MERCH] )                       -- merchandise only (fuel QUANTITY is not an item count)

Baskets = DISTINCTCOUNT ( FactSales[BASKET_ID] )

Households = DISTINCTCOUNT ( FactSales[household_key] )

Basket Value = DIVIDE ( [Sales], [Baskets] )

Sales per Household = DIVIDE ( [Sales], [Households] )

Units per Basket = DIVIDE ( [Units], [Baskets] )

Gross Value = SUM ( FactSales[GROSS_VALUE] )                  -- shelf value before retailer discounts

Retail Discount = - SUM ( FactSales[RETAIL_DISC] )
Coupon Discount = - SUM ( FactSales[COUPON_DISC] )
Coupon Match Discount = - SUM ( FactSales[COUPON_MATCH_DISC] )

Retail Discount Depth % = DIVIDE ( [Retail Discount], [Gross Value] )
Coupon Discount Depth % = DIVIDE ( [Coupon Discount], [Gross Value] )

Private Label Share % =
DIVIDE ( CALCULATE ( [Merch Sales], DimProduct[BRAND] = "Private" ), [Merch Sales] )

Share of Merch Sales % =
DIVIDE ( [Merch Sales], CALCULATE ( [Merch Sales], ALL ( DimProduct ) ) )

Sales Prev Week =
VAR wk = SELECTEDVALUE ( DimWeek[WEEK_NO] )
RETURN CALCULATE ( [Sales], DimWeek[WEEK_NO] = wk - 1 )

WoW Change % = DIVIDE ( [Sales] - [Sales Prev Week], [Sales Prev Week] )

Running Total Sales =
VAR wk = MAX ( DimWeek[WEEK_NO] )
RETURN CALCULATE ( [Sales], DimWeek[WEEK_NO] <= wk, ALL ( DimWeek ) )

Sales 4wk Moving Avg =
VAR wk = MAX ( DimWeek[WEEK_NO] )
RETURN
    AVERAGEX (
        FILTER ( ALL ( DimWeek[WEEK_NO] ), DimWeek[WEEK_NO] > wk - 4 && DimWeek[WEEK_NO] <= wk ),
        [Sales]
    )

Sales Y1 Window = CALCULATE ( [Sales], DimWeek[growth_window] = "Y1 window (wk 24-49)" )
Sales Y2 Window = CALCULATE ( [Sales], DimWeek[growth_window] = "Y2 window (wk 76-101)" )
Growth Y2 vs Y1 % = DIVIDE ( [Sales Y2 Window] - [Sales Y1 Window], [Sales Y1 Window] )

Commodity Rank in Dept =
IF (
    ISINSCOPE ( DimProduct[COMMODITY_DESC] ),
    RANKX ( ALLSELECTED ( DimProduct[COMMODITY_DESC] ), [Merch Sales], , DESC, Dense )
)

Promoted Sales % =
DIVIDE (
    CALCULATE ( [Merch Sales], FactSales[promo_status] IN { "Display only", "Mailer only", "Display + Mailer" } ),
    CALCULATE ( [Merch Sales], FactSales[in_causal_scope] = 1 )
)

Targeted Households = DISTINCTCOUNT ( FactCampaignTarget[household_key] )
Redeeming Households = DISTINCTCOUNT ( FactCouponRedemption[household_key] )
Redemptions = COUNTROWS ( FactCouponRedemption )
Redemption Rate % = DIVIDE ( [Redeeming Households], [Targeted Households] )

Households (RFM) = COUNTROWS ( DimHousehold )
Segment Sales = SUM ( DimHousehold[total_sales] )
Segment Sales Share % = DIVIDE ( [Segment Sales], CALCULATE ( [Segment Sales], ALL ( DimHousehold[segment] ) ) )
Demographic Coverage % = DIVIDE ( CALCULATE ( [Households (RFM)], DimHousehold[has_demographics] = 1 ), [Households (RFM)] )

Forecast = SUM ( FactForecast[forecast] )
Actual (holdout) = SUM ( FactForecast[actual] )
Abs Error = SUMX ( FactForecast, ABS ( FactForecast[actual] - FactForecast[forecast] ) )
MAPE % =
AVERAGEX (
    FILTER ( FactForecast, NOT ISBLANK ( FactForecast[actual] ) ),
    DIVIDE ( ABS ( FactForecast[actual] - FactForecast[forecast] ), FactForecast[actual] )
)
```

Note on the campaign measures: Redemption Rate % divides *distinct* households. If several campaigns are selected at once, a household is counted once across them. That is why the per-campaign rates in the report come from the SQL table `r_campaign` (one campaign at a time).

## 4. Control totals (check your model against these)

With no filters applied, the cards must show:

| Measure | Expected value | Source |
|---|---|---|
| Sales | $8,057,463.08 | r_kpi_overview.total_sales |
| Merch Sales | $7,381,574.35 | r_kpi_overview.merch_sales |
| Units | 3,345,344 | r_kpi_overview.merch_units |
| Baskets | 275,903 | r_kpi_overview.baskets |
| Households | 2,500 | r_kpi_overview.households |
| Basket Value | $29.20 | r_kpi_overview.avg_basket_value |
| Retail Discount Depth % | 14.78% | r_kpi_overview.retail_disc_depth_pct |
| Redemptions | 2,318 | r_coupon_totals.redemption_rows |

## 5. Dashboard layout (5 pages)

Use one consistent page header: title on the left, slicers in a single row underneath (Department, Week range, Brand).

**Theme: black, white and grey only.** Import `BW_PowerBI_Theme.json` (View → Themes → Browse for themes). It sets a white background, black text and a grey-scale series palette. When a chart has two series, use dark grey for the main one and light grey for the comparison. Use line style (solid / dashed / dotted) to tell lines apart instead of colour.

**Page 1: Executive overview**
- KPI cards: Sales, Merch Sales, Baskets, Basket Value, Sales per Household, Retail Discount Depth %
- Line chart: Sales by DimWeek[WEEK_NO], with a constant line or shaded band marking the ramp-up (weeks 1-16)
- Bar chart: Merch Sales by DimProduct[DEPARTMENT] (top 10)
- Text box: "Weeks 1-16 = households still joining the panel; compare like-for-like windows (wk 24-49 vs 76-101)"

**Page 2: Merchandising and assortment**
- Matrix: DEPARTMENT → COMMODITY_DESC with Merch Sales, Units, Share of Merch Sales %, Private Label Share %, Growth Y2 vs Y1 %, Commodity Rank in Dept
- Clustered bar: Private Label Share % by DEPARTMENT
- Two tables: top 10 growers and top 10 decliners (filter: Sales Y1 Window ≥ 10,000; sort by Growth Y2 vs Y1 %)
- Slicer: BRAND

**Page 3: Promotions and campaigns**
- Clustered column from PromoLiftSummary: unit_lift_pct and sales_lift_pct by promo_status
- Card: Promoted Sales %; bar: Retail Discount Depth % by FactSales[promo_status]
- Table: DimCampaign campaign_type, CAMPAIGN, Targeted Households, Redeeming Households, Redemption Rate %
- Footnote (text box): "Promo flags exist for 115 of 582 stores and weeks 9-101 only. Lift is descriptive, not causal."

**Page 4: Customer segments (RFM)**
- Clustered column: Households (RFM) share vs Segment Sales Share % by segment
- Table: segment, Households (RFM), Segment Sales, avg baskets, avg recency_days
- Stacked bar: Merch Sales by segment × DEPARTMENT (100% stacked)
- Card: Demographic Coverage % (say "demographics available for 801 of 2,500 households")
- Slicers: INCOME_DESC, AGE_DESC (exclude "Not available" with a filter if desired, and say so on the page)

**Page 5: Forecast and data quality**
- Line chart: FactForecast actual vs forecast by WEEK_NO (filter mode = "fixed origin (wk 89)"; method slicer)
- Table: method, MAPE %, Abs Error (one row per method)
- Table: DataQualityLog (rule_id, action, rule, rows_affected, sales_affected)
- Card: "Sales reconcile to raw: $8,057,463.08 before and after cleaning"
