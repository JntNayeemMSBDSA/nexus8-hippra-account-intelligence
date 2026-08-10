# HIPPRA Tableau Build Guide — click-by-click

## 0. Build contract

Use only `<NEXUS_PROJECT_ROOT>/13_tableau_preparation/hippra_tableau_prep_20260810T213214Z/hippra_tableau_account_360.csv`. It has exactly **88,986 rows at one row per certified commercial account**: 83,367 physician groups, 5,432 hospitals and 187 health systems. The source passed uniqueness, completeness, cross-format reconciliation, serviceability coverage, enrichment reconciliation and fail-closed postal-geocoding checks.

Audience: an executive or commercial-analytics reviewer who needs to understand account coverage, network structure, enrichment coverage and records needing review. This workbook is descriptive. Do not label any view TAM, SAM, SOM, revenue, forecast, customer, contract, priority or eligibility.

## 1. Connect and lock the data source

1. Open Tableau Desktop or Tableau Public.
2. Under **Connect**, click **Text File**; choose `hippra_tableau_account_360.csv`; click **Open**.
3. Rename the data source at the upper left to `HIPPRA Certified Account 360`.
4. On the Data Source page choose **Extract**, not Live. Then click the first worksheet tab. Tableau documents text-file connections and Extract mode [here](https://help.tableau.com/current/pro/desktop/en-us/examples_text.htm); extracts are the recommended performant path for file-based data [here](https://help.tableau.com/current/pro/desktop/en-us/perf_extracts.htm).
5. Confirm the row indicator is **88,986**. If not, stop.
6. Assign geographic roles: right-click **Geocode State** → Geographic Role → State/Province; **Geocode Postal Code** → Zip Code/Postcode; **Geocode Country** → Country/Region. Do not assign a geographic role to Postal Code Original.
7. Save immediately as `HIPPRA_Account_Intelligence_v1.twbx` inside `<NEXUS_PROJECT_ROOT>/13_tableau_preparation/hippra_tableau_prep_20260810T213214Z`. Do not publish yet.

## 2. Create these calculated fields exactly

For each item choose **Analysis → Create Calculated Field**, paste the formula, then click **OK**. Select fields from Tableau autocomplete if your display capitalization differs.

**Account Count**
```tableau
COUNTD([Commercial Account Id])
```

**Provider-Account Relationships**
```tableau
SUM([Provider Relationship Count])
```

**Accounts with Providers**
```tableau
COUNTD(IF [Unique Provider Count] > 0 THEN [Commercial Account Id] END)
```

**Enriched Accounts**
```tableau
COUNTD(IF [Has Targeted Enrichment] THEN [Commercial Account Id] END)
```

**Enrichment Rate**
```tableau
COUNTD(IF [Has Targeted Enrichment] THEN [Commercial Account Id] END)
/
COUNTD([Commercial Account Id])
```

**AHRQ System-Linked Hospitals**
```tableau
COUNTD(IF [Has Ahrq Health System Link] THEN [Commercial Account Id] END)
```

**Review-Attention Accounts**
```tableau
COUNTD(IF [Review Attention Required] THEN [Commercial Account Id] END)
```

**Review-Attention Rate**
```tableau
COUNTD(IF [Review Attention Required] THEN [Commercial Account Id] END)
/
COUNTD([Commercial Account Id])
```

Format both rates as Percentage with one decimal. Keep counts as whole numbers with thousands separators. Do not use SUM on portfolio-wide constant fields; they exist only as reconciliation anchors.

## 3. Apply the visual system once

- Dashboard size: **Fixed 1440 × 900**. Tableau recommends setting size before layout; use tiled horizontal/vertical containers [as documented here](https://help.tableau.com/current/pro/desktop/en-us/dashboards_organize_floatingandtiled.htm).
- Palette: navy `#093B58` for titles/primary marks; orange `#DA5810` for review attention; teal `#1DA39D` for certified/enriched; light gray `#D9D9D9` for dividers; white `#FFFFFF` background.
- Font: Tableau Book or Arial. Dashboard title 24 pt bold; section titles 14 pt bold; KPI values 28–32 pt; labels 10–11 pt.
- Use color plus text/shape, never color alone. Avoid red/green meaning. Remove gridlines, zero lines and heavy borders. Use 16 px outer padding and 8 px between objects.
- Keep every worksheet title action-oriented, every tooltip short, and every axis starting at zero for bars.

## 4. Build the worksheets

Create and rename sheets in this order.

### KPI — Accounts

1. Marks → **Text**. Drag **Account Count** to Text.
2. Edit text to `Certified Accounts` on line 1 and the value on line 2. Center; navy value.

Duplicate it six times and replace the measure to create: `KPI — Physician Groups` (filter Account Type), `KPI — Hospitals`, `KPI — Health Systems`, `KPI — Provider Relationships`, `KPI — Enriched Accounts`, and `KPI — Review Attention`.

### Account Mix

1. Rows: **Account Type**. Columns: **Account Count**. Marks: Bar.
2. Sort descending; Show Mark Labels; color navy. Title: `What types of accounts are certified?`

### Serviceability Evidence

1. Rows: **Broad Account Status**. Columns: **Account Count**. Marks: Bar.
2. Use navy bars; label counts; sort descending.
3. Tooltip: Broad Account Status, Account Count, Serviceability Evidence Completeness, Broad Status Reason.

### Geographic Coverage

1. Double-click **Geocode State**. Marks: Map.
2. Drag **Account Count** to Color and Label; **Account Type** to Detail; **Geocode Country** to Detail.
3. Use a single sequential navy palette. Keep unknown locations hidden only from this map, never from the source.

### Top Accounts by Provider Relationships

1. Rows: **Account Name**. Columns: **Provider-Account Relationships**. Marks: Bar.
2. Add Account Type to Color; Commercial Account Id and Unique Provider Count to Tooltip.
3. Filter Account Name → **Top** → By field → Top 15 by SUM(Provider Relationship Count).
4. Sort descending. Title: `Which accounts have the most provider relationships?`

### Enrichment Coverage by Account Type

1. Rows: **Account Type**. Columns: **Enrichment Rate**. Marks: Bar.
2. Add **Enriched Accounts** and **Account Count** to Tooltip. Format rate as percent; color teal.

### Network Structure

1. Rows: **Account Name**. Columns: SUM(**Direct Child Account Count**).
2. Filter to Direct Child Account Count > 0. Keep Top 15 by SUM(Direct Child Account Count).
3. Add Direct Parent Account Count, Child Relationship Types and AHRQ Health System Names to Tooltip.

### Review Queue

1. Filter **Review Attention Required** to True.
2. Marks → Text. Place Account Name, Account Type, State, Review Attention Reason, Candidate Relationship Count, Serviceability Evidence Completeness and Commercial Account Id on Rows, in that order.
3. Fit Width; alternate row banding; no aggregation for text fields. Title: `Which certified accounts still need evidence review?`

### Account Explorer

1. Marks → Text. Add Account Name, Account Type, Account Subtype, City, State, Postal Code Classification, Unique Provider Count, Broad Account Status, Has Targeted Enrichment, AHRQ Health System Names and Commercial Account Id to Rows.
2. Fit Width; sort Account Name ascending. Keep this as the lowest-detail sheet.

## 5. Add global filters correctly

On `Account Mix`, drag Account Type, State, Broad Account Status, Has Targeted Enrichment, Has AHRQ Health System Link and Review Attention Required to Filters. Show each filter. For each card choose **Apply to Worksheets → Selected Worksheets**, then select every analytical sheet except the fixed methodology text. Official multi-worksheet filter behavior is documented [here](https://help.tableau.com/current/pro/desktop/en-us/filtering_global.htm).

Use compact dropdowns. Do not use “Only Relevant Values” unless necessary; it can add query cost. Six global filters is the maximum for this workbook.

## 6. Assemble three dashboards

### Dashboard 1 — Executive Account Landscape

1. New Dashboard → Fixed 1440 × 900 → Tiled.
2. Outer vertical container: title (64 px), KPI horizontal strip (150 px), main horizontal section (420 px), footer (50 px).
3. KPI strip: Accounts, Physician Groups, Hospitals, Health Systems, Provider Relationships, Enriched Accounts, Review Attention.
4. Main section: Account Mix (35%), Serviceability Evidence (30%), Enrichment Coverage (35%).
5. Footer text: `Certified descriptive account coverage; source periods vary. No market sizing or forecast.`
6. Put Account Type, State and Broad Account Status filters in a narrow right-side vertical container.

### Dashboard 2 — Network and Geography

1. Title and three KPI cards: Accounts with Providers, Provider-Account Relationships, AHRQ System-Linked Hospitals.
2. Main row: Geographic Coverage (55%) and Top Accounts by Provider Relationships (45%).
3. Bottom row: Network Structure (50%) and Enrichment Coverage by Account Type (50%).
4. On Geographic Coverage and Top Accounts, click the sheet menu → **Use as Filter**. Tableau filter actions are documented [here](https://help.tableau.com/current/pro/desktop/en-us/actions_filter.htm).

### Dashboard 3 — Data Quality and Account Explorer

1. Top text block: `QA PASS | 88,986 unique accounts | CSV/Parquet/DuckDB reconciled | missing is never treated as zero`.
2. Main row: Review Queue (45%) and Account Explorer (55%).
3. Add filters: Account Type, State, Postal Code Classification, Review Attention Required.
4. Add a text box titled `Methodological boundaries` with these bullets: certified system is DuckDB + Parquet/CSV; source periods vary; candidate relationships are not final; missing values remain null; SQL Server reconstruction is incomplete and separate.

## 7. Tooltip and interaction standard

Use this pattern: bold account name; account type and geography; provider relationship count; serviceability status; enrichment types; review reason; then `Account ID: <id>`. Do not expose long source-lineage JSON. On Dashboard → Actions, keep only intentional Filter or Highlight actions; Tableau’s action types and execution behavior are documented [here](https://help.tableau.com/current/pro/desktop/en-us/actions.htm).

## 8. Mandatory reconciliation before you send the workbook back

Clear every filter and verify:

- Account Count = **88,986**
- Physician Group count = **83,367**
- Hospital count = **5,432**
- Health System count = **187**
- Data Source row count = **88,986**
- No map uses Postal Code Original.
- Review Attention is labeled as a quality/review flag, never sales priority.
- Missing/unknown categories remain visible in bar charts and tables.

Then run **Server → Run Optimizer**, address safe “Take action” items, and review every other recommendation. Tableau explains the Optimizer [here](https://help.tableau.com/current/pro/desktop/en-us/wbo_overview.htm). Test every filter, action, tooltip and dashboard at 100% zoom. Save the packaged workbook, but do not publish it or upload it to GitHub yet.

## 9. Return for final QA

Send Codex the finished `.twbx` (preferred) or `.twb` plus its extract. Final QA will check formulas, totals, filters, actions, accessibility, layout, performance, methodological labels and source-path portability. GitHub publication happens only after that QA passes.
