# User review and revision scope

This is a consolidated record of the user's dictated review and accepted direction on September 20, 2026, not a verbatim transcript. Codex remains the primary development assistant. Implementation and model-comparison results are recorded separately; agreement on scope is not a claim that the work has passed validation.

## Product direction

- Build an internal question-and-answer workspace with clearly distinguished question, answer, and evidence. Use familiar navigation and a neutral, high-contrast palette; remove slogans and repetitive feature explanations. Do not imply that independent questions share conversational memory.
- Keep source file and author/attendee attribution visible beside each claim. Underlined source links open an accessible citation dialog with the exact selected passage, metadata, location, full extracted content, and original download. Remove the persistent evidence sidebar.
- Add a simple Documents screen for browsing source content and enrichment, plus drag-and-drop and file-picker ingestion of supported transcript and Office formats. Report actual per-file results and unchanged duplicates. Preserve original files, versions, attribution, and previous answer evidence.
- Keep the existing 24-document corpus as the fresh-setup default. Provide two additional fictional transcripts outside automatic ingestion, with sample downloads and before/after questions. Uploaded files persist; restart must not discard user work. Arbitrary supported documents may be uploaded, with extraction/attribution limitations reported honestly.
- Provide concise, discoverable workspace context explaining the fictional consultancy, three engagements, and corpus contents.
- Add a small developer playground for retrieval and answer APIs, with actual responses and copyable curl commands. Retrieval-only requests must not manufacture answers or knowledge gaps. Retain the existing command-line ingestion and interactive API documentation.
- Separate operational readiness, ingestion outcomes, and answer-evaluation findings. The review queue remains for knowledge gaps and consumer rejection/correction. There is no requirement for a human to approve every ingested document.

## Model selection direction

Accuracy takes precedence over latency and modest cost differences. The previous three failed semantic cases out of 15 are release blockers, not an acceptable trade for a cheaper model. Include GPT-5.6 Luna, DeepSeek, Kimi, and representative frontier models, keeping GPT-4.1-mini as a comparison baseline. Verify actual provider availability and compatible structured-output settings.

Define and freeze expected facts, source evidence, scope, contradictions, abstentions, and enrichment expectations before benchmark calls. Preserve failed results. Distinguish existing regression cases from newly held-out questions. Compare actual application behavior, not only token prices or general-purpose leaderboards. Measure generation, verification, retrieval, and enrichment separately enough to attribute failures correctly. Reference labels and semantic inspection must not depend solely on the application's model judge.

The first comparison pass had a USD 15 spending ceiling, announced before execution. After initial frontier costs were measured, the user explicitly approved a USD 40 total benchmark ceiling, including the initial spending, for a fuller comparison and repeats. Latency can increase to support correct answers, within explicit operational bounds. The selected configuration must pass the defined release suite; a finite suite cannot establish universal correctness. Publish the measured rationale, actual model/provider parameters, costs, latency, and limitations in the repository.

## Development boundaries

UI work, document/search APIs, and the benchmark are implemented in parallel with explicit file ownership. Root integration owns provider compatibility, quality summaries, final configuration, validation, and publication. Runtime data, paid-call ledgers, credentials, and unrelated personal files stay outside Git; selected redacted benchmark reports use only fictional corpus material. Reused OpenAI documentation guidance is copied under `.agents/skills/openai-docs`, alongside earlier skill provenance snapshots.
