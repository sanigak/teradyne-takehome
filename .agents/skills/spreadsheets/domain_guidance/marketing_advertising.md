## Marketing/Advertising Guidance

Additional guidelines for marketing, advertising, campaign, funnel, lead, CRM, growth, attribution, ROI, or web/ad performance workbooks

If any specific rule conflicts with user's request or reference, always prioritize the user's request first, then reference/template then general defaults.
Formatting must always be consistent throughout the workbook.

For read-only questions, inspect relevant source records, calculations, definitions, units, periods and protocols without modifying/exporting, changing inputs, adding helper fields/checks or refreshing sources. Report gaps and failed checks rather than repairing them. Authoring defaults apply only to requested creation or edits; preserve original source records and narrow-edit scope.

Distinguish extract freshness from analysis time, and trace requested campaign, channel or funnel outputs to their calculations and sources while preserving the comparison basis.

### Tab structure

- Keep source data, analysis and stakeholder outputs clearly distinguishable without treating those roles as mandatory tabs. Use separate sheets when import/refresh boundaries, calculations, different readers or an explicit request justify them; a compact report may combine compatible roles in labeled regions while preserving the raw data.
- Clearly name tabs by content (e.g., “Leads_Q1_2025”, “Pipeline Analysis”, “ROI Dashboard”) so that users can easily find inputs versus results.

### Cell formatting

- Highlight key performance metrics to make them stand out. Use consistent coloring or emphasis for important numbers. For instance, you might shade cells green for metrics that hit target and red for those below target.
- Include a color key with text to ensure meaning is clear
- Bold fonts and borders can draw attention to total figures or summary KPIs.
- Input cells (e.g., cells where a user can adjust an assumption like a growth rate or a budget allocation) can be given a distinct fill color (such as light yellow), so that planners know what fields they can edit.
- For metrics, ensure formatting matches common practice and is legible, e.g. percent metrics with one decimal and a % sign, currency with appropriate symbols and no excessive decimals, and so on, for professional appearance.
- If the spreadsheet serves as a report, you should incorporate the company’s branding colors in charts or headers.

### Marketing Analysis

- Formula clarity is important. Keep formulas straightforward (SUMIFS, COUNTIFS) and avoid overly complex nested IF logic for scenarios. Instead, consider a separate table mapping conditions to outcomes.
- Leverage pivot tables or summary functions to aggregate data by campaign, channel, etc., rather than a tangle of manual formulas.
- Keep time-series dates typed and consistently formatted. Add an ISO export/helper column only when a downstream interface requires it and the requested scope permits it; do not convert the working date axis to text or add unused helpers.

### Raw data vs. outputs

- Keep raw data, including import data, intact and separate from any modifications
- Any cleaning (like removing test entries or combining categories) should be done in an adjacent column or in a processing sheet, so the original dump remains as a source of truth. Then use references or pivot tables to feed your analysis. This way, if new data arrives (say, next month’s metrics), you can paste it into the Data tab and refresh the analysis easily.
- Output figures should follow traceable calculations from the intact sources, whether those roles occupy separate sheets or clear regions on one sheet.
- Include a chart or compact visual only when it clarifies the requested trend, comparison or funnel. Keep its source ranges traceable; do not create a separate dashboard or hide supporting data merely to satisfy this example.

### Metadata and sources

- Marketing analytics often involves combining data from multiple sources (ad platforms, surveys, sales figures). Always document these sources. For example, label a data column “Facebook Ads – Impressions (source: Ads Manager export on 2025-05-01)” or have a small note on the dashboard: “Data Sources: Google Analytics, CRM database (as of Apr 2025).” This gives context to the numbers and their freshness. Include time frames and units in your labels – e.g., “Budget (USD)” or “Weekly Reach”.
- Label any assumptions clearly
- Consistency is also key: if “CPC” means cost per click, ensure it’s defined somewhere or obvious from context, so everyone reading the sheet interprets metrics correctly.
