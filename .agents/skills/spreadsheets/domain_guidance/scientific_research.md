## Scientific Research Guidance

Additional guidelines for scientific research, experiments, lab measurements, surveys, statistical analysis, reproducibility, protocol, or raw/processed research data workbooks.

If any specific rule conflicts with user's request or reference, always prioritize the user's request first, then reference/template then general defaults.
Formatting must always be consistent throughout the workbook.

For read-only questions, inspect relevant source records, calculations, definitions, units, periods and protocols without modifying/exporting, changing inputs, adding helper fields/checks or refreshing sources. Report gaps and failed checks rather than repairing them. Authoring defaults apply only to requested creation or edits; preserve original source records and narrow-edit scope.

### Tab structure & naming

- Keep raw observations intact in a clearly identified flat table, with one variable per column and one observation per row. Raw, processed and results are distinct roles, not a mandatory number of worksheets.
- Put cleaning or transformations in separate columns/regions or a processed-data sheet when needed; never overwrite original measurements. Choose separate sheets for substantive transformations, refresh boundaries, reproducibility or review needs, and preserve the requested source layout.
- Document cleaning steps and protocol in an existing appropriate region or a dedicated sheet when their extent warrants it. Add Calculations or Results sheets only for a distinct analytical or reader purpose, not to expand a simple raw-data export.

### Formatting

- Each column should contain one type of data (with units in the header, not mixed into the cells) and each row one record.
- Avoid merging cells or creating multi-row headers that can complicate data import into analysis tools.
- Do not use formatting (color, bold, italics) as the sole means to encode information in data tables as analytical software may not recognize cell color. Instead, if certain values need flagging (e.g. outliers or notable entries), add a separate “Flag” column or annotation.
- Layout should be plain and data-focused: for instance, list any comments or notes in a separate column rather than as Excel cell comments or text boxes. This makes the data more machine-readable.

### Formula practices

- In scientific spreadsheets, complex data analysis is often done outside Excel, but when using formulas, prioritize transparency and accuracy.
- Avoid volatile functions (e.g. RAND() for randomization) unless necessary for simulation, and document any usage clearly.
- Do not introduce circular references; iterative calculations can obscure the lineage of results and complicate reproducibility.
- If performing calculations like statistical formulas or unit conversions in-sheet, show the formula or use helper columns for each step so others can verify the math. This stepwise approach makes it easier to verify scientific calculations. Where possible, cross-check important calculations with another tool or manual calculation and state any limitation. Preserve the recorded protocol, source units and original measurements; distinguish flags, missing observations, simulation/randomness and assumptions without silently changing the analysis design.
