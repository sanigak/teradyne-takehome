# Style and Formatting Instructions

Follow user instructions, then intentional templates/references, then domain guidance. Defaults apply only to new sheets or authorized restyling.

Render before editing. Preserve unrelated content, layout, formatting and native features; values-only edits must not change formatting.

## Tab Structure Defaults
- Order and group tabs by reader workflow. Keep primary views and related working sheets together; group supporting calculations, checks and sources separately when separate tabs are needed.
- Keep needed assumptions/guidance accessible. 
- Add divider tabs only when useful in complex workbooks; leave ordinary tabs uncolored but add consistent tab color when it aids navigation.

## Reader-facing sheet layout

For new reader-facing sheets or authorized restyling, default to a compact reader-facing layout.

- Use a concise unfilled left-aligned title, thin rule, short context/subtitle and modest whitespace before the main content. Avoid large filled title banners.
- Keep the title stack short; move detailed sources, caveats and maintenance notes to an existing Sources/Notes area or side area.
- Add summary/KPI cards only when they clarify the requested decision; do not duplicate a small table or make oversized cards.
- Choose cards, tables and charts for the task; keep useful trends and comparisons rather than defaulting every summary to a table.

## Use a visually clear layout
- Distinguish headers, inputs, calculations and notes consistently. Default to dark body text and restrained fills, not a universal teal theme; preserve domain styling defaults, like finance input/formula/source colors and dynamic statuses.
- Use modest spacing and consistent row heights, especially within the same section. Expand for wrapped content; format only populated or intentionally reserved ranges.
- Keep working titles, headers and input/calculation areas unmerged. Presentation merges require user/template intent; never overwrite content or combine distinct table columns. For requested spanning headers, use supported Center Across Selection over otherwise empty cells.
- For new reader-facing sheets or authorized restyling, use a compact table-first front page: concise unfilled title, short context line, modest whitespace, then the decision/table. Do not replace it with a large filled banner or KPI-card grid unless requested or it clearly improves the decision.
- Use yellow/amber for inputs needing updates; follow documented exception styles for overrides, special formulas and one-offs. Label failed checks; add a compact legend when colors have multiple meanings.
- Dark column headers: white text with thin white separators between actual headings, including dates.
- Section bands: continuous fill and one outside outline, without internal borders; exclude gutters.
- If a sheet uses a leading gutter, keep it consistent: align titles, sections and tables to the same content edge; do not use gutter columns for notes, units or data.
- Prefer thin/light structural borders, stronger section breaks and no full body-cell grid. Do not apply borders around every filled cell. 
- Hide gridlines where styling defines reader-facing structure; retain useful working gridlines.
- Put needed context in separate cells or ordinary punctuation. Preserve meaningful financial/mathematical labels and symbols, required source quotes, intentional reference conventions and the expressly specified plain `x` navigation markers;
- Conditional Formatting is preferred over manually painted cells when applying styles consistently over a range, column or table.
- Use bounded conditional formatting for dynamic status, risk, priority, variance, threshold and exception cues when they aid scanning or must react to edits; do not use it for decoration or substitute static fills.

## Freeze panes

- Freeze rows/columns only when they keep useful headers or identifiers visible while scrolling, using the smallest useful frozen area. Leave enough space to read and work with the data.
- Do not move content or add tabs to accommodate freezing. Preserve existing panes during unrelated edits.
- Do not freeze compact summary, dashboard or cover sheets unless scrolling requires preserving shared headers or row labels.

## Align and format by data type

- Left-align text, right-align numbers and center column headers horizontally/vertically. Top-align wrapped descriptions where helpful.
- Keep numbers/dates typed with explicit, appropriate formats and clear units. Adjust widths/heights so final content with formatting fits (including signs, parenthesis and units); never stringify values for appearance.
- Italicize brief context/scope/unit notes—not headers, controls, statuses or warnings.

## Use typography intentionally but conservatively

- Resolve fonts once: use the first verified in both generating and target environments, Helvetica Neue → Helvetica → Arial → Aptos. Record availability and fallbacks; unverified does not mean unavailable.
- Use one family across cells, charts and theme fonts, with consistent body sizing. Keep titles and key metrics only modestly larger; spacing and restrained fills can be used for hierarchy.
- Keep font sizes consistent and the same outside of visual dashboard/hero tabs and headers or titles.
  - Do not vary font size of rows inside the same table.
  - If specific rows or column callouts are needed, use bold/italics sparingly. For example for totals or when needed for domain styling defaults.

## Live inputs and visuals

- Drive dependent values, charts and status text from editable cells. Use conditional formatting for useful status/exception cues and categorical validation where feasible. Invalid/missing inputs must not appear as plausible zeros or success states.
- Prefer compact, formula-linked summaries. Preserve required outputs; avoid redundant tables and oversized KPI cards. Inline bars require explicit request. Follow `features/charts.md` for charts.

## Verification

Inspect the saved workbook at normal zoom, with cells unselected. Check every tab for consistency, readable wrapping and unclipped content. Verify live states, conditional-format ranges, effective fonts and saved freeze panes.
