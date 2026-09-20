# Relay AI — delivery knowledge workspace

A local knowledge application for a fictional AI-deployment consultancy. Ask a question across meeting transcripts and Office documents, inspect the evidence behind each claim, and route unresolved questions to source authors or meeting attendees. Team leads review gaps and corrections; routing drafts go to an explicitly simulated outbox.

Built for the three exercises in [the take-home brief](Teradyne_FDE_Take-Home_Exercises.pdf). All client, employee, and business data is invented.

Public repository: [sanigak/teradyne-takehome](https://github.com/sanigak/teradyne-takehome).

[![Checks](https://github.com/sanigak/teradyne-takehome/actions/workflows/checks.yml/badge.svg)](https://github.com/sanigak/teradyne-takehome/actions/workflows/checks.yml)

## Run locally

Prerequisites: Python 3.14+, Node.js 24 LTS, and LibreOffice. Git is needed to clone the submission. No database server, Office license, Docker, or email account is required. OpenRouter credentials and account credits are required for ingestion and answers.

```bash
git clone https://github.com/sanigak/teradyne-takehome.git
cd teradyne-takehome
```

### Windows PowerShell

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
```

Set `OPENROUTER_API_KEY` in Windows user/system environment variables, or copy `.env.example` to `.env` and set it there. Never commit the credential. The Windows scripts refresh this specific variable from the saved environment, so an existing terminal can pick it up. If your convention uses another variable, set `OPENROUTER_API_KEY_ENV` to its name before invoking the scripts.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 ingest
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 serve
```

Open **http://127.0.0.1:8000**. The interactive API documentation is at **http://127.0.0.1:8000/docs**. Keep the server terminal open. The process-scoped execution-policy argument lets the checked-in scripts run without changing your system policy.

If LibreOffice is installed somewhere else, set `SOFFICE_PATH` to its `soffice.com` executable. Scripts also detect a portable copy under `.tools/libreoffice/program`. Node can similarly be installed normally or placed under `.tools/node-*-win-x64`.

### Linux

Install Python 3.14, Node.js 24, and LibreOffice using your preferred package manager; on Ubuntu, LibreOffice is available as `sudo apt-get install libreoffice`.

```bash
bash scripts/setup.sh
# Set OPENROUTER_API_KEY in the environment or a local .env file.
bash scripts/run.sh ingest
bash scripts/run.sh serve
```

Use `PYTHON=/path/to/python3.14 bash scripts/setup.sh` when necessary. `SOFFICE_PATH` can override the detected LibreOffice executable. Environment files are loaded by the backend, never shipped to the browser.

## Try the workflow

For an ordered hands-on rehearsal, use the [30–45 minute UI/CX review queue](docs/UI_REVIEW_QUEUE.md). The [adversarial testing record](docs/ADVERSARIAL_TESTING.md) separates reproduced failures, fixes, automated checks, and live-model limitations.

1. Ask **“What is Atlas Forge's current launch date, and what changed from kickoff?”** Open a citation to compare source dates and the changed decision.
2. Ask **“Explain Atlas's staged rollout and latency stop condition, including whether the workbook contains measured latency.”** Inspect the presentation and workbook evidence.
3. Ask **“What is the weather vendor's signed deletion SLA for Beacon Route?”** Review the missing information and evidence-backed routing, edit the message, and save it to the simulated outbox.
4. Correct or reject an answer with a comment. Open **Review Queue**, inspect the original answer and citations, then resolve it with a note.

The application calls OpenRouter; it does not substitute canned answers when credentials are absent. Without configuration the interface remains accessible and explains what is missing. Sending to the outbox does **not** deliver email.

### Call the API

```bash
curl http://127.0.0.1:8000/api/health
curl -X POST http://127.0.0.1:8000/api/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is Atlas Forge current launch date?"}'
```

For PowerShell, use `Invoke-RestMethod` to avoid native-shell JSON quoting differences:

```powershell
$body = @{ question = 'What is Atlas Forge current launch date?' } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/query -Method Post -ContentType application/json -Body $body
```

See [API contract](docs/API_CONTRACT.md) for response shapes and feedback, source, review, outbox, and quality endpoints.

## Data and design

The committed corpus contains 24 distinct files: 12 Markdown transcripts and two of each `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, and `.xlsx`. It spans Atlas Forge, Beacon Route, and Cedar Vale. Source attribution is embedded in the documents and checked against a manifest. The corpus specification and generator are committed so reviewers can inspect and reproduce the fictional material.

The Python service extracts structured locations, preserves author/attendee identities, enriches all formats with the same model instructions, and stores versioned records in SQLite. Full-text retrieval and embeddings retrieve candidate passages. An assessment first checks which requested facts are available without seeing a proposed answer; generation then selects source spans and writes cited claims, followed by a separate support check. Quotations come directly from stored source text. Generation/enrichment use `openai/gpt-4.1-mini`; coverage and verification use configurable `openai/gpt-4.1`, chosen after live testing. Model-based checking reduces errors but is not a proof of factual accuracy.

Original files and query snapshots are retained under `.runtime`. Updating a source creates a new active version without breaking earlier citations. Re-ingestion skips unchanged content under the same extraction, prompt, and model profile. It reports failures per file and keeps previously successful versions available.

An explicit folder ingestion synchronizes that folder: deleted or renamed paths are retired from active retrieval, while their historical evidence and archived downloads remain available. Sources with recognizable instructions aimed at controlling the answering model are excluded from answers and routing, with visible health warnings. This conservative screening is not a general guarantee against poisoned source facts.

Read [architecture and tradeoffs](docs/ARCHITECTURE.md), [evaluation approach](docs/EVALUATION.md), [AI development record](docs/AI_WORKFLOW.md), and the [exercise checklist](docs/EXERCISES.md).

## Verify

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 test
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 ui-test
```

The equivalent Linux commands are `bash scripts/run.sh test` and `bash scripts/run.sh ui-test`. The wrapper discovers portable Node on Windows and keeps commands at the repository root. Browser tests use test-only network fixtures. No mocked model exists in the runtime application.

With the key configured, explicitly verify live model access, ingest the corpus, and evaluate:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 smoke
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 ingest
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 evaluate
# In a separate terminal while the service is running:
.venv\Scripts\python.exe scripts/smoke.py
```

Direct Python invocations require a terminal that has inherited the key, or a local `.env`. The live evaluation exits unsuccessfully if its assertions fail. Deterministic CI runs without credentials; a separate manually triggered GitHub Actions workflow can run live evaluation using a repository secret.

## First 30 days

Track **answer rejection/correction rate**: the number of distinct answered query IDs receiving rejection or correction divided by the number of answered query IDs in the first 30 days. Count partial responses containing supported claims as answers, deduplicate repeated feedback, and exclude evaluation traffic. Persist queries and feedback to calculate the rolling measure through `/api/metrics`; review failures alongside the original evidence. Voluntary feedback can miss problems and is not an unbiased accuracy estimate.

## Boundaries

This is a local, single-user evaluation application. It binds to loopback, has no authentication or client isolation, and does not send real email. Cloudflare exposure is outside this version. Extraction covers document text, tables, presentation text/notes, and workbook cells; it does not perform OCR, interpret embedded objects, or recalculate uncached Excel formulas. Missing values and extraction warnings are surfaced rather than invented.

Reused development guidance is included under `.agents/skills`; these are guidance snapshots, not runtime dependencies. The application runs entirely from the checked-in project and normally installed prerequisites. Environments, downloaded tools, credentials, build outputs, and runtime databases are intentionally excluded from Git.
