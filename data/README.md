# Fictional Relay AI corpus

All people, client engagements, contracts, and incidents in this dataset are invented. The corpus contains exactly 24 distinct documents: 12 meeting transcripts and two of each `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, and `.xlsx` extension. Legacy files are genuine compound Office binaries exported with LibreOffice; they are not renamed OOXML archives. All source files carry visible authors, dates, attendees, and document classification.

`corpus/` is the only directory passed to ingestion. `manifest.json` holds expected attribution, document hashes, warnings, and known facts; `evaluation.json` holds the evaluation questions. Keeping these files outside the ingestion directory prevents evaluation answers from becoming retrieval evidence.

The three fictional engagements cover Atlas Forge's maintenance-manual assistant, Beacon Route's depot forecasting pilot, and Cedar Vale's administrative policy assistant. The material includes provisional decisions later superseded, an unresolved contradiction between two approved Beacon acceptance thresholds, genuinely missing contractual and policy facts, numerical targets versus observations, and attributable owners for follow-up questions.

Regenerate with `python scripts/generate_corpus.py --soffice /path/to/soffice`. The generator source defines all document content and formatting. It creates modern Office files with the project Python dependencies and converts independent content into legacy binaries using an isolated LibreOffice profile. It verifies each file's author, attendees, and date after extraction before publishing the manifest. Repeated generation reproduces content and structure; Office archive/container metadata may change file hashes.

The evaluation set is fixed, is never supplied to answer or enrichment prompts, and is not a statistical estimate of production accuracy. Its first three cases form the daily canary: a supported answer, a partial answer for conflicting evidence, and an answerable ownership route for a missing fact. Run the complete suite before submission or when changing retrieval, prompts, or models.
