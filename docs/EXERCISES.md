# Exercise acceptance map

| Requirement | Implementation | Reviewer check |
| --- | --- | --- |
| Empty new workspace and AI-assisted development | New repository, original brief, local rules and guidance, development record | Inspect AGENTS.md and AI_WORKFLOW.md |
| Generated organization corpus | 24 distinct committed source files and regeneration script | Inspect data/corpus and data manifest |
| Transcript ingestion and enrichment | CLI folder ingestion, source attendees/date, shared enrichment prompt | Ingest transcript folder, inspect `/api/sources` |
| Structured storage and natural-language API | SQLite documents/chunks/query snapshots and `POST /api/query` | Run curl example or scripts/smoke.py |
| Office formats alongside transcripts | Genuine modern and binary Word, PowerPoint, Excel fixtures | Run extraction tests and full ingestion |
| Traceability for every answer claim | Validated chunk IDs, evidence quotations, file/version, native locator, attribution | Click each citation in Ask |
| Evidence-based routing | Author/attendee candidates from relevant chunks and editable message | Ask Beacon vendor SLA question |
| Capture corrections and gaps | Original query and answer snapshots; review, gaps, feedback APIs | Reject/correct then open Review Queue |
| Detect quality degradation | Held-out evaluation, failed-case gates, recurring canaries, quality API/UI | Run evaluation; inspect alerts and failing-test scenario |
| Working web application | React app served from the same FastAPI origin | Build and open local URL |
| Review edit send | Editable recipient/subject/body and persisted simulated outbox | Save and inspect routed message |
| Team-lead review | Open/resolved queue with resolution notes and original evidence | Resolve a gap and reopen its details |
| First-month measurement | One-paragraph definition in README and implemented counters | Inspect `/api/metrics` |
| Public repository submission | Full source, data, tests, instructions, and reusable development artifacts | Clone public repository and run setup |

The outbox deliberately simulates sending, as selected during planning. Real email delivery is not claimed.
