# Beacon Route — pilot acceptance decision

Date: 2026-09-11
Author: Priya Raman
Attendees: Priya Raman; Noah Brooks; Jules Park
Client: Beacon Route
Domain: Model evaluation
Priority: High
Classification: SYNTHETIC — fictional evaluation material

Transcript — edited for clarity; all people and engagements are fictional.

Noah Brooks: After deduplication, the held-out forecast error is 11.4 percent on the two-depot sample. The historical seasonal spreadsheet baseline was 16 percent. These are percentage MAE results, not classification accuracy.

Jules Park: Planners can work with that if the run arrives on time. A perfect model after the morning staffing decision is useless.

Priya Raman: Decision: accept the Beacon pilot only when mean absolute percentage error is at most 12 percent, forecasts arrive by 06:00 local depot time, and missing-input runs fall back to the seasonal baseline with a warning.

Noah Brooks: I own measuring forecast error and freshness. The evaluation set is frozen at eight holdout weeks; training must not include those weeks. We have not measured live operational savings yet.

Jules Park: Decision: every forecast requires manual planner approval. An abstention or fallback should explain which inputs are missing and name the depot.

Priya Raman: Action: Noah posts the acceptance workbook before September 13. Jules leads five morning rehearsals. Commercial signature remains separate from technical acceptance.
