# Corporate Finance / FP&A Guidance

Make FP&A workbooks readable, refreshable, auditable, and useful for decisions.

## Priority And Overrides

Prioritize user intent, then the supplied workbook/template/screenshot/style guide, then these defaults. The selected skill/workflow governs tools, verification, completion and final responses.

For read-only questions, inspect/reconcile values, periods, sources and controls without new tabs, input changes, checks/helpers/comments, refreshes or repairs. Apply only nonmutating checks in `financial_models.md#required-audit-pass`, not authoring/input perturbations. Creation defaults never authorize restructuring a narrow edit.

## When To Use

Use for budgets, forecasts, long-range/operating plans, business reviews, KPI packs, headcount/opex/revenue/cash planning, leadership-review cleanup and recurring or cross-functional workbooks. Use `financial_models.md` for DCF, LBO, 3-statement, comps and investment-banking models.

## Deliverable Standard

Provide readable hierarchy, drivers and units; straightforward refreshes; traceable assumptions, links, checks, versions and sources; and decision-useful variances/takeaways.

## Do No Harm

Apply `../workflows/edit_workflows.md`, including protected reporting/query blocks and authorized row/column additions. Preserve version, refresh, source, scenario and period conventions. State ambiguous placement assumptions and choose the least-disruptive location. Use separate analysis only when needed and authorized, preserving reporting/collection logic; read-only and narrow formatting tasks do not authorize tabs.

## Workbook Structure

Needed roles may share regions. One cost build may split into personnel/nonpersonnel for distinct drivers, then component builds/rollups as data/workflow require. Preserve sourced drivers, schedules, references and `financial_models.md#on-timeline-and-actuals-vs-forecast`; adapt existing layouts.

- `Summary`: KPIs, variances, period and units. Month/case controls must change the requested view; maintenance metadata belongs in Sources/guide unless requested here.
- `Assumptions`: primary driver grid and separate setup controls per the finance timeline guidance.
- `Data_Links`: imports, mappings, source references and refresh controls.
- `Operational_Drivers`: volume, price, mix, headcount, unit cost and timing.
- `Forecast_Model`: monthly/quarterly calculations.
- `Variance_Analysis`: actual vs budget/forecast/prior year. Inspect dependencies before consolidating a distinct monthly calculation schedule feeding comparisons.
- `Dashboard`: executive charts and summary tables.
- `Scenarios`: case tables, selector logic and sensitivities.
- `Checks`: sheet/workbook controls.
- `Sources`: reports, extract dates, owners and source notes.

Only when user/reference requires this sequence, place substantive `Cover`, summary, assumptions and schedules before one `Internal >>`, `Checks`, `Sources`. Follow `../style_guidelines.md#tab-structure-defaults`: internal/source separation has no tab minimum; keep simple workbooks proportional and edits scoped.

Inventory source-backed scenario, owner, status, assignment, action and payment controls across all applicable rows/sections. Verify saved validation type, visible dropdowns, complete row coverage, source-approved finite bounds and unchanged existing rules. Assign full ranges through the workflow's documented API/schema; do not invent collection setters.

Keep units visible in approved helpers, labels, headers or legends; hiding helpers requires express authorization and equivalent context. Preserve provenance, asset permissions, calculations, checks, unrelated content and input privacy.

## FP&A Formatting Defaults

Unless user instructions or existing conventions override them:

- Follow `financial_models.md#workbook-layout-and-structure` for working sheets, centered case values and optional rows.
- Label units, e.g. `Revenue ($000s)`, `GM (%)`, `Headcount (FTE)`, `AR Days`.
- Apply finance timeline/`financial_models.md#number-formatting` rules: 0–1 currency decimals by scale, one percentage decimal and decision-useful operational precision.
- Use whitespace/selective borders. Hide summary/dashboard gridlines only when styling supplies structure; data/input tabs may retain them.

## Periodicity And Time Axis

Apply `financial_models.md#on-timeline-and-actuals-vs-forecast` to calendars, Assumptions, scalar controls, cases, adjustments and tests across Actual/Budget/Forecast/Prior Year. Use the needed grain, usually monthly, with quarter/year rollups in separate blocks/sheets. Extend formulas/formats consistently across periods.

## Inputs, Calculations, And Outputs

Apply default formula rules; keep calculations readable left to right with few tab jumps. Outputs prioritize management KPIs, trends, variances and drivers. Mark distributed input zones with nearby instructions.

Use the finance layout rules for one authoritative selector and linked displays. State its scope: a report-month selector may change summaries, not an all-month owner log/full forecast. Apply shared control/dependent-state styling; calculated indices are not inputs. Move helpers to existing support areas only when authorized.

Match monthly metrics, rankings, charts and commentary to the selected period, using linked or period-neutral narration. Keep owner commentary/actions keyed to stable business identifiers and periods as records move/arrive. Align imports, calculations and review tables; flag missing/duplicate keys rather than guessing.

## Variance Analysis

Default order: `Actual | Budget/Forecast | Var $ | Var % | Prior Year`; include only relevant columns.

Keep variances beside comparisons and label favorable/unfavorable direction. Separate price, volume, mix, rate and timing or use waterfalls when useful; totals/sub-bridges reconcile to reported variance.

Headline monetary variances need amount and percent on the same labeled basis and clear expense over/under-budget direction. Missing/zero denominators mean unavailable, not 0%; do not mix monthly export budgets with unrelated annual plans.

Business reviews connect supported actuals/drivers to forecast implications and a next action/owner question. Label proposals and missing owner input, not implied commitments.

## Reporting And Dashboards

Work backward from the management question. Show KPIs, trend, variance and 2–4 main drivers. Follow [Summary/KPI placement](financial_models.md#workbook-layout-and-structure) and the main skill's Writing Quality and Authored Content section: clear findings/implications/actions, setup/diagnostics in support, material limitations beside results.

Apply `../features/charts.md`; use combo value/percent charts, waterfalls, actual/target bullets, sparklines or conditional formatting when helpful. Avoid 3D/overcrowding; title metrics/units and keep labels readable in PDF/print.

## External Data And Refresh Discipline

Centralize imports/links in an identifiable region or a tab justified by dependencies, refresh or scope; preserve source-owned tabs/workflows. Avoid unnecessary or scattered live links; keep retained ones findable, testable and repairable. Tie actuals to management-reporting controls.

Record verified systems/reports, as-of/refresh dates and manual mappings. Source freshness differs from build time; unknown dates remain unknown, not today. Keep paste/update instructions near data.

For recurring/rolling forecasts, append complete periods or merge extracts on existing period/business keys without losing history or double-counting overlaps. Preserve schema; disclose capacity/range extensions. Derive actual cutoff from the latest complete valid source period or validate a required manual cutoff against it.

Keep assumptions, scenarios, explanations and events tied to absolute periods as horizons advance. Do not roll headers over stationary inputs or require owners to shift retained entries left. Preserve narrow-edit conventions; report conflicting designs instead of restructuring.

Match instructions to saved formulas/ranges. On an authorized disposable copy, test a new actual period and dated future adjustment through outputs, checking history, date/case mapping, tail periods and roll-forwards; discard/restore afterward. Distinguish inspection, cache and executed recalculation; unrun refreshes are unverified.

## Checks And Controls

Apply `financial_models.md#checks-and-additional-verification-guidance`. Persistent checks/status need concrete risk or recurring use. If combined status is useful, PASS requires all required checks to pass; show failures/fix locations using needed fields, or `None`.

Check source ties, period aggregation, valid scenarios, headcount/opex/revenue/cash roll-forwards, alternate cuts, populated/bounded assumptions, signs and variances.

Inspect reported controls, source vs build dates, period/case/output/narration agreement and relevant reconciliations. Report missing/failed checks and unverifiable source/owner metadata; author/repair only when authorized.

## Sources, Versions, And Metadata

Use a Sources table such as:

`Item | Value | Units | Period/As-of | Source Type | Source Name | Ref | Owner | Notes | Accessed/Refreshed (YYYY-MM-DD)`

Use the main skill's Citation Requirements for compact explanations in ordinary cells, or in notes/comments only when requested:

`Source: <system/report/document> | As-of: <YYYY-MM-DD> | Ref: <page/tab/field> | Notes: <short>`

For estimates:

`Assumption: <reason> | Owner: <role> | Date: <YYYY-MM-DD>`

Keep useful version/refresh/owner/scenario metadata and material assumption-change notes in Sources/guide, not default summary banners. Keep material dates, periods, units and limitations beside affected analysis.

Verify owners/dates and distinguish proposed/accepted owners. Omit immaterial unknowns or label material gaps; never invent metadata.

## Definition Of Done

Outputs answer the question with presentation-ready summaries, consistent period/status labels and unmixed core grain. Forecasts pass `financial_models.md#on-timeline-and-actuals-vs-forecast` grid/control checks. Inputs are obvious, calculations hide no hardcodes, and major inputs/adjustments are sourced or marked assumptions. Imports/links are centralized/documented; controls pass or failures are explained. Metadata/source dates remain available without redundant banners, and period/case context and warnings match inputs.
