# Financial Modeling Guidance

## Scope And Priority

Use for 3-statement, DCF, LBO, debt, operating, scenario, sensitivity, comps/valuation models, finance dashboards and institutional/analyst/board/IC/lender-quality work, including assumptions, timelines, checks and sources. Also read `corporate_finance_fpa.md` for budgets, forecasts, reviews, KPI packs and headcount/opex/revenue/variance plans.

Exclude generic trackers, planners, rosters, surveys and project logs unless finance styling is requested. Precedence: user > reference/template > finance defaults. Keep formatting consistent.

Read-only work permits inspection/analysis, not new tabs/helpers/comments/checks, input changes, repairs or export. Authoring/audits remain within requested scope; no unrelated repairs or restructuring.

## Reference following: Company-specific model translation

Preserve reference analytical depth and layout. Map material drivers/schedules to company equivalents using reported KPIs, guidance and primary disclosures, not generic growth/margin assumptions when specific drivers exist. Disclose/justify material omissions or simplifications; reference formatting takes priority.

## Row And Cell Classes

Classify before styling:

- `title`: model/report names.
- `metadata`: version, date, author, currency, units, scenario and source/as-of context.
- `table_column_header`: a data-column label, including periods; not a section, input or body-row label.
- `period_header`: calendar, fiscal, actual, estimate, forecast or scenario-period labels.
- `section_header`: major block labels.
- `subheader`: labels within a section.
- `body`: calculation, source or data rows.
- `total`: totals, subtotals, ending balances, key outputs, checksums or valuation lines.
- `input`: editable assumptions/drivers.
- `linked_imported`: formulas/values from other sheets, files, systems, filings or datasets.
- `check`: statuses, deltas, tie-outs, warnings and sanity checks.
- `spacer_note`: separators, footnotes, source context, explanations and caveats.

A one-cell section label is not a period header; titles and metadata are not table headers.

## New creations and defaults

### Formatting Rules

#### Worksheet Tabs

Group primary views with related working sheets and supporting calculations/checks/sources separately; keep assumptions/guidance accessible. Named dividers must clarify substantial-workbook groups, not force extra sheets or a fixed sequence.

Reserve pale tan for a primary Assumptions tab if needed. Ordinary tabs stay uncolored; support groups/dividers need navigation value or an approved reference, not all-tab role colors.

#### Default sheet structure

Use consistently on new financial-model/report tabs and authorized restyling, including related working/data tabs; Checks may use a diagnostic layout. Exclude raw/import/staging, logs, compact tables, simple calculators and covers. Other types need user/reference intent.

- Use narrow empty leading gutters, normally A:B with content in C. Preserve intentional single gutters and navigation markers. Align titles, sections, tables, notes and units to the chosen content edge; only actual gutters stay empty.
- Row 1 is blank. Row 2 has a concise left-aligned title, consistent capitalization and a continuous thin bottom border across the working width. Row 3 is an optional italic, non-bold subtitle adding context. Rows 4–5 are blank; rows 6–7 hold needed short headers, units, controls or periods, followed by data. Do not invent calendars.
- Comparable time-based tabs share one typed calendar in row 6/7, referenced by calculations/checks; avoid lower repeats while preserving distinct frequencies.
- Put sources/caveats/maintenance notes in existing Sources/Notes or a readable labeled side area with a gutter, not the title stack/new tab for a few notes. Do not widen the working grid; retain nearby controls, flags, checks and dependencies.

#### Color Formatting Conventions

- **Blue text (RGB: 0,0,255)**: Editable numeric assumptions, scenario drivers and manual inputs, including pasted actuals intended for manual refresh. Role, not historical date, determines input styling; immutable imports, filing constants, IDs, labels, dates, metadata and source values are not blue unless editable.
- **Black text (RGB: 0,0,0)**: Same-sheet body formulas/calculations.
- **Green text (RGB: 0,128,0)**: References to other worksheets in this workbook.
- **Red text (RGB: 255,0,0)**: External file links.
- **Yellow background (RGB: 255,255,0)**: Assumptions needing attention or updating.

Dark headers use white text even for linked/calculated dates; header contrast overrides body colors. When colors have multiple input/formula/link meanings, include a compact legend matching actual styles.

#### Number Formatting

Set explicit number/date formats on source values and formula outputs, with numbers right-aligned. Use [Finance period labels](#on-timeline-and-actuals-vs-forecast) for calendars, source grain and status.

Classify units and row roles first. Show currency symbols on the first monetary row of each section/roll-forward, main monetary lines, subtotals/totals and ending monetary balances, across every populated actual/estimate period. Supporting detail normally uses compatible number-only formats. First/last/bold status does not make headcount, percentages, runway months or ratios monetary.

The four primary presets are Number, Dollar, Percentage (one decimal) and Indent. Numeric presets share positive; negative; zero; text sections. These USD defaults keep `$ X` near the amount, negatives in parentheses and zero as a plain dash without `$` or `%`. Use source/user currency; if absent, use neutral units or label an assumed currency. Formatting must not imply FX conversion or change values/units.
  ```text
  Currency, opening/main/ending: _("$"_* #,##0_);_("$"_* (#,##0);_(* "-"_);_(@_)
  Numbers, supporting amounts/counts: _(* #,##0_);_(* (#,##0);_(* "-"_);_(@_)
  Percentages: _(* 0.0%_);_(* (0.0%);_(* "-"_);_(@_)
  ```

Indent supporting labels/commentary beneath headings with ` @` (one leading space and `@`; Excel may save `\ @`). Keep headings/main/total/ending labels flush left, using weight/borders for hierarchy. Do not insert spaces into stored labels or formulas, double-apply format padding/alignment indentation, or break formula-linked commentary. Inspect wrapped indentation in native Excel.

Multiples are optional, not a fifth primary preset:
  ```text
  Multiples: _(* 0.0"x"_);_(* (0.0"x");_(* "-"_);_(@_)
  ```

Preserve literal format tokens: `_x` reserves the next character's width, so `_*` is fixed padding; `* ` repeats spaces. Swapping them moves the currency symbol. Keep compatible right-edge padding and verify native appearance.

Normally use zero decimals for whole-unit amounts/integer counts, one for percentages and two for per-share prices; fractional FTEs, rates and scaled amounts may need more. Change only numeric placeholders, preserving negative/zero/text/padding sections and visible currency/scale. Never round stored values or treat missing data/untested checks as zero. Do not add `[Red]` automatically; preserve intentional negative-color conventions without overwriting input/link/calculation meanings.

After export, test representative first/main/detail/ending rows across actual/estimate columns, with positive, negative, zero and text values. Negative percentages must show `(5.0%)`, not `(5.0)%`. Inspect native symbol placement, dash alignment, indentation and vertical alignment: middle for single-line numeric grids; top for wrapped descriptions/related cells when helpful. Preserve typed values, formulas, periods and units. Accepted format strings do not prove native appearance; mark unavailable native checks unverified.

Optional compact scales:

For base-unit Number/Dollar values, replace only `#,##0` in positive/negative sections with the appropriate placeholder. Default to one decimal, with extra precision optional. Keep suffixes inside negative parentheses and preserve padding, dash-only zero and text sections.

| Display scale | Replacement numeric placeholder |
| --- | --- |
| Thousands (K) | `#,##0.0,"K"` |
| Millions (M) | `#,##0.0,,"M"` |
| Billions (B) | `#,##0.0,,,"B"` |
| Trillions (T) | `#,##0.0,,,,"T"` |

The base-unit Dollar/M format is `_("$"_* #,##0.0,,"M"_);_("$"_* (#,##0.0,,"M");_(* "-"_);_(@_)`. Choose commas from stored units: thousands need one comma to display millions. Do not double-scale, change/round values or formulas, or apply amount scales to percentages/labels. Keep currency/units clear and verify exported displays.

### Workbook Layout and Structure

Organize needed roles around readers, dependencies and refresh; roles may share regions. One cost build may split into personnel/nonpersonnel for distinct drivers, then component builds/rollups as data/workflow require. Preserve sourced drivers, requested sheets, schedules, references and narrow-edit structure.

Show formula-linked outputs, material assumptions and implications in a summary region; separate tabs need reader/workflow/reference justification. Narrow edits preserve sheets. Anchor assumptions to history, sources or visible ramps/steps; Covers need a distinct requested purpose.

Keep useful KPI cards in the summary view, not across working schedules. Use tables/charts, side by side when helpful; honor dashboards/references. Include relevant checks, e.g. balance-sheet balance.

For substantial new/authorized restructured models, apply `../style_guidelines.md` and needed controls/navigation across related regions/sheets. Preserve references, occupied cells and raw/import/staging schemas; compact generic tables/full-bleed covers need no finance scaffolding.

- Use job-specific titles and consistent peer Title Case unless the reference differs; preserve successful header geometry when removing banners.
- Retain useful selectors/instructions, a gap before controls and aligned units/periods. One authoritative case/reporting selector drives linked displays. Center case values horizontally/vertically, preserving labels, styling and dropdowns; do not recenter numeric inputs or invent cases. Remove repeated month displays only without reader/control purpose; highlighting/comparison context counts. Clearing a display never authorizes deleting its row/selector. Keep setup/detail below headers without displacing periods.
- Bound multipart legends or use a separate line; never overflow into controls or widen the period grid.
- Useful note/context outlines in wide models start expanded. Never group mixed rows containing selectors, current case, status, warnings or headers; safely separate controls only when authorized, otherwise leave ungrouped. Preserve references/validation, recheck panes after moves and italicize notes without weakening controls/warnings.
- Eligible new working sheets default to two visible narrow gutters, for example A:B at width 2 with content in C. Preserve source widths, single gutters, occupied columns and authentic logos. On long model/build/assumption sheets needing navigation, use faint but visible lowercase `x` cells in both gutters for genuine major sections and the first only for subsections. The first is the all-section elevator, the second major-section express elevator for Control/Command+Down Arrow. Use the chosen font and readable size. Do not invent sections, mark body rows, use formula/hyperlink markers, or add markers to short outputs, covers or raw grids. Preserve approved markers and occupied/protected cells.
- Follow `#on-timeline-and-actuals-vs-forecast` for shared periods. Non-time headers, distinct frequencies, reference and print-header requirements remain exceptions; recheck downstream references when consolidating rows.
- Within this finance/reference profile, use one label per section, two blank body-height rows between major sections and one shorter blank row below each label, throughout the model. Preserve raw schemas, occupied reference cells and narrow-edit scope; this spacing is not for generic tables.
- Preserve added-input provenance in a compact source table/existing documentation and retain supported annotations. Follow the main skill's Citation Requirements: new comments/notes require a request; narrow edits do not force a source table.
- State relevant currency/scale, fiscal basis, forecast period, valuation/source dates, scenario and discounting conventions. Label units in headers/rows. Compact summaries need no Units column merely repeating formats: use a brief italic shared currency/scale line and distinct-unit labels, preserving required schemas/material differences.
- Wrap long text; keep source/history/notes readable at normal zoom. Use compact source IDs/aliases in rows, full URLs in existing documentation or needed/requested Sources. Record item, value, units, period/as-of, link and notes without repeating long URLs.
- Maintain a version history/changelog for repeated requested iterations.

Group new/authorized restructured workbooks by workflow, not tab thresholds/divider ratios; preserve requested names/order and reference navigation. Follow [Worksheet navigation](../style_guidelines.md#tab-structure-defaults). Small workbooks need no dividers merely for internal roles. `Internal >>`, `Outputs >>`, `Builds >>` are optional examples; use clear labels, not duplicate summaries.

Apply [Worksheet Tabs](#worksheet-tabs), reserving tan for a primary Assumptions tab if needed. Preserve schedules, sources, formulas, protections and scope. Under `../SKILL.md` Verification Rules, verify saved order/dividers, widths, markers, titles, selective colors and supported native persistence; all-tab coloring is not grouping.

#### For 3-statement or IB-style models

Use explicit forecast drivers, not hardcoded outputs. Roll retained earnings through beginning balance, net income, distributions, repurchases and other equity movements; tie cash-flow ending cash to balance-sheet cash. Make debt, cash and share schedules explicit when they affect valuation. A balance-sheet check cannot pass merely because cash/equity/other is plugged; label and justify unavoidable plugs.

#### On Timeline and actuals vs forecast

For period-based models:

- Apply [Clean headers/gutters](../style_guidelines.md#use-a-visually-clear-layout) and [Freeze panes](../style_guidelines.md#freeze-panes). Match comparable tabs' period columns/order/grain; reserve descriptor space, not shifted periods. Link to a shared calendar in an existing sheet; no mandatory calendar tab. Record source, frequency, reference and scope exceptions.
- Visually separate history/forecasts and keep copy-across formulas consistent. Separate monthly/quarterly/annual blocks with clear rollups. Source/user instructions govern history, cutoff, horizon and grains. New multi-grain blocks run annual, quarterly, then monthly with one empty gutter unless the reference differs; never invent grains.
- New/restructured forecasts need a primary assumptions region or justified tab matching model typed dates/order/grain/start/end: drivers down rows, periods across. A static list with dated inputs elsewhere fails. Preserve inputs' absolute dates as the window advances, retaining prior periods as needed.
- Give each recurring driver an independently editable cell per forecast period, repeating a supported flat default without invented variation. Static value/case-only columns cannot replace the date grid. Use only source/requested cases. Two or more cases keep each case row's full date axis and a formula-driven `Selected Case` row above, controlled by one valid selector; single cases still need period-specific inputs.
- Link downstream inputs by matching period/selected case with supported nonvolatile formulas; never bypass the grid with an anchored scalar. Preserve source grain. Separate genuinely nonperiod setup, opening state and scenario-wide policies such as runway hurdles, with one editable control per applicable case and linked repeated displays. Do not create unread monthly hardcodes or replace recurring-driver rows with these scalars.
- Label adjustments as one-time, recurring or changing future run-rate/growth base. Preserve source treatment; identify any additional assumption when the source is silent.
- Verify assumptions/model dates match one-for-one without gaps, duplicates or reorderings. Trace controls to final calculation/decision outputs, not only input mirrors. Test a later-period driver and each distinct control type: legitimate later roll-forwards may change, earlier periods/unrelated drivers may not. Restore inputs and recheck outputs. Tie statements to the selected period, reconcile approved aggregates and confirm case changes affect only intended estimates.

Use finance/reference labels `MMM:YY` (`Aug:26`), `QX:YY` (`Q3:26`) and `FY:YY` (`FY:26`) consistently across Assumptions, Forecast, comparable tabs and charts, preserving intentional user/reference alternatives.

Keep real dates/date-returning formulas in the canonical calendar. Monthly display is `mmm":"yy`; quarter/fiscal labels follow the source fiscal calendar. Excel has no generic quarter token, so derive linked labels while retaining calculation dates. Never expose a sorting-anchor year as a reporting year. Request a necessary missing year/fiscal basis or leave labels explicitly unresolved; that check has not passed.

Follow [Clean headers and gutters](../style_guidelines.md#use-a-visually-clear-layout) for alignment/borders. Dark headers use white text over body input/link colors, including linked dates. Distinguish Actual/Budget/Forecast through grouping bands, labels or restrained related fills with equal font sizes/stable geometry. Stacked statuses share neutral period labels. Only requested/reference-established A/E suffixes use `Aug:26A` / `Aug:26E`, with `mmm":"yy"A"` / `mmm":"yy"E"`; never derive status from today's date or formula origin.

Verify native displayed labels, quarter/fiscal boundaries, December-to-January rollover, alignment and borders. Preserve typed values, formulas, source periods and successful alignment independently of other layout defects.

### Formula Rules

Apply the main skill's Formula Correctness guidance; for existing workbooks, preserve [editing scope](../workflows/edit_workflows.md#formula-rules).

Use standard Excel/financial functions when auditable: NPV/XNPV, IRR/XIRR, PMT/IPMT, SLN/DB/DDB and exact-match INDEX/MATCH or XLOOKUP. Avoid volatile `INDIRECT`/`OFFSET` unless required; total with SUM across the range above, not a line-skipping sum of parts. External links need explicit request/existing presence; unavoidable links are labeled red.

Circular references require intentional finance logic, such as sweeps, average-balance interest or working-capital loops. Document purpose, configure iteration and disclose in place or existing Checks; no hacks. Guard return formulas until cash-flow signs/minimum data are valid. An illustrative template lacking valid IRR/XIRR should use a documented cash-on-cash estimate, NPV at the stated rate or guarded RATE approximation, not `#NUM!`.

### Sensitivity/scenario table correctness

Label changed drivers in row/column headers. Every output calculates from those inputs and the target output or equivalent logic, recalculating underlying valuation/return mechanics rather than tweaking final values. Never paste static sensitivities. Reuse mechanics/intermediates in a small labeled block near the grid; do not repeat the whole model per cell or add sensitivity-only helper tabs.

### DCF and valuation minimums

For DCF/valuation, IB and equity research, show valuation, needed sensitivities/scenarios, checks and Sources/Audit in suitable regions or justified tabs. Unless requested otherwise, include revenue/EBIT or EBITDA drivers, taxes, D&A, capex, change in NWC, unlevered FCF, discount factors, PV of FCF, terminal value/PV, enterprise value and an equity bridge when net debt/share data exists. Label source gaps/simplifications without unsupported precision. State Gordon-growth or exit-multiple terminal value; discount it using forecast cash-flow timing. Follow the sensitivity rules.

### Investment Banking Guidance

Without a supplied reference/template, IB-style LBO, DCF, 3-statement and valuation models hide gridlines, use horizontal borders above totals across label/value columns, and restrained dark section bands with white text across intended content width. Follow [Freeze panes](../style_guidelines.md#freeze-panes) for scrolling models, keeping inputs, identifiers, periods and decision metrics visible. Organize needed helpers/approved check-only outlines in place under `Checks` guidance.

## Editing or formatting existing workbooks

Apply `../workflows/edit_workflows.md` to formatting/restyling. Preserve correct formats, freeze panes, filters, grouped headers and date/period semantics unless explicitly changed. Analysis sheets need an authorized analytical purpose; formatting-only edits and read-only questions do not authorize them.

Classify rows from labels, existing formats, nearby context and sample values before formatting ranges. Only genuine margin, rate, growth, yield, WACC/TGR, cost of equity/debt, discount, risk-free, risk-premium or tax-rate rows receive percentage treatment.

## Required Audit Pass

Source-backed analyses and high-impact models need relevant evidence inspection beyond formula-error scans. Within authorized scope, trace sources/assumptions/high-impact formulas to drivers; reconcile present income statements, balance sheets, cash flows, valuation, sensitivities/scenarios and checks. Explain large forecast/history step-changes or report gaps; confirm plugs are labeled/justified. Inspect numeric completeness/types, signs, units, source periods and controls. Distinguish missing inputs from valid zero and cached status from executed tests.

This inspection does not authorize writes or input perturbation. Report uncertainty/differences without new checks, helpers, comments or repairs. During requested source-backed authoring, linked models, valuation or forecasting, additionally fix material unexplained changes within scope, bridge their drivers or add source/assumption context. Keep calculations traceable without adding unrelated helpers/repairs to narrow edits.

### `Checks` and Additional Verification Guidance

- Verify formula errors, required input/source completeness, component totals and material signs/units; preserve required independent controls. Persistent checks need concrete risk or recurring use; in-place checks may suffice. Test distinct input rules and material downstream outputs, reusing representative tests where logic is shared. Preserve required independent financial reconciliations.
- Compute shared validation once in suitable regions; link output status/counts only for reader need, not repeated grids. Keep material failures and editable workflow statuses visible; these rules concern calculated helpers.
- Keep helpers in existing areas within authorized scope; link in-place checks to central views only if needed. Preserve approved outlines; add only when useful and authorized, without blanket hiding. Group helper axes, not periods to hide rows. Inputs, IDs, units, metrics, statuses and warnings stay visible.
- Checks have one owner and acyclic dependencies: inputs/metrics/helpers feed Checks, which feed summaries, never back into themselves. Display links do not duplicate logic. Use in-place assertions or needed Actual/Expected/Difference/Tolerance/Status/Notes fields. Any combined status aggregates statuses, not business logic, with clear formatting; show failures/fix locations.
- Test each editable control type through downstream outputs with invalid/missing, zero and boundary inputs. Derive bounds from the math, including valid/nonzero denominators and positive values where required. Reject invalid inputs or show non-PASS, never plausible zeros. Expose forecast formula errors in outputs and any model status. On a safe native copy, test failure propagation and relocated/collapsed checks, saved outline state and expand/collapse; restore inputs. Cached PASS is not verification; missing/untested checks cannot pass, and unavailable native tests are not run. Preserve narrow-edit scope.
- Check cross-input feasibility: for additive nonnegative flows, annual assumptions cannot imply a negative remainder after reported year-to-date actuals. Preserve signed/net-flow conventions and actuals; expose infeasible assumptions instead of changing history.
- IB/3-statement/operating checks cover applicable balance-sheet balance, cash and debt roll-forwards, signs, subtotal tie-outs and revenue/margin sanity. Valuation checks tie FCF to components, validate discount factors/terminal value and enterprise-to-equity bridges, and reject hardcoded key outputs.
- After bulk formatting, check representative labels against formats so rates/percentages and date headers were not turned into currency/plain numbers. Before finalizing, inspect representative formulas/styles/colors, resolve scoped high-priority findings and report verified results or limitations. Retain the selected skill's verification and completion rules in `../SKILL.md`.
