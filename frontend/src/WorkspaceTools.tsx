import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { Check, Copy, FileText, LoaderCircle, Upload, X } from "lucide-react";
import { api, post } from "./api";
import type { Quality, SourceDocument, UploadSample } from "./api";

export function EvaluationDetails({ quality }: { quality: Quality }) {
  const reports = quality.suites?.length
    ? quality.suites
    : quality.latest
      ? [quality.latest]
      : [];
  return (
    <details className="quality-details">
      <summary>Latest evaluation details</summary>
      <div className="evaluation-reports">
        {reports.map((report, i) => (
          <section key={i}>
            <h4>{String(report.suite || "Answer evaluation")}</h4>
            <dl className="source-metadata">
              <div>
                <dt>Passed</dt>
                <dd>
                  {typeof report.passed === "number" &&
                  typeof report.case_count === "number"
                    ? `${report.passed} of ${report.case_count} cases`
                    : "See evaluation findings"}
                </dd>
              </div>
              {typeof report.dataset === "string" && (
                <div>
                  <dt>Dataset</dt>
                  <dd>{report.dataset}</dd>
                </div>
              )}
              {typeof report.created_at === "string" && (
                <div>
                  <dt>Run time</dt>
                  <dd>{new Date(report.created_at).toLocaleString()}</dd>
                </div>
              )}
              {typeof report.model === "string" && (
                <div>
                  <dt>Model</dt>
                  <dd>{report.model}</dd>
                </div>
              )}
            </dl>
          </section>
        ))}
      </div>
    </details>
  );
}

export function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const root = document.getElementById("root");
    const previousInert = root?.inert || false;
    if (root) root.inert = true;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = () =>
      [
        ...(ref.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]',
        ) || []),
      ].filter((element) => element.getClientRects().length > 0);
    focusable()[0]?.focus();
    const listener = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close.current();
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", listener);
    return () => {
      document.removeEventListener("keydown", listener);
      document.body.style.overflow = overflow;
      if (root) root.inert = previousInert;
      if (previous?.isConnected) previous.focus();
      else
        document
          .querySelector<HTMLElement>('.nav-item[aria-current="page"]')
          ?.focus();
    };
  }, []);
  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <section
        className={`workspace-modal ${wide ? "wide-modal" : ""}`}
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-heading">
          <h2>{title}</h2>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label={`Close ${title === "Service details" ? "status" : title === "Source evidence" || title === "Review source evidence" ? "evidence" : title}`}
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </section>
    </div>,
    document.body,
  );
}

export function FullDocument({ documentId }: { documentId: string }) {
  const [document, setDocument] = useState<SourceDocument | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const generation = useRef(0);
  async function load() {
    const current = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const value = await api<SourceDocument>(
        `/sources/${encodeURIComponent(documentId)}`,
      );
      if (current === generation.current) setDocument(value);
    } catch (e) {
      if (current === generation.current) setError((e as Error).message);
    } finally {
      if (current === generation.current) setBusy(false);
    }
  }
  useEffect(() => {
    generation.current += 1;
    setDocument(null);
    setError("");
    setBusy(false);
    if (open) void load();
  }, [documentId]);
  return (
    <details
      className="full-document"
      open={open}
      onToggle={(event) => {
        const next = event.currentTarget.open;
        setOpen(next);
        if (next && !document && !busy && !error) void load();
      }}
    >
      <summary>Full extracted document</summary>
      {busy && <p role="status">Loading document…</p>}
      {error && (
        <div className="notice error" role="alert">
          {error}
          <button className="text-button" onClick={() => void load()}>
            Retry document
          </button>
        </div>
      )}
      {document && (
        <>
          <p className="muted">
            {document.active
              ? "Current source version"
              : "Historical source version"}
            . Layout follows extracted text; download the original for its
            native formatting.
          </p>
          {document.warnings?.map((warning, i) => (
            <p key={i} className="notice warning">
              {warning}
            </p>
          ))}
          {document.chunks.map((chunk) => (
            <section className="document-passage" key={chunk.chunk_id}>
              <h4>{chunk.locator}</h4>
              <p>{chunk.text}</p>
            </section>
          ))}
          {document.versions && (
            <details>
              <summary>Version history ({document.versions.length})</summary>
              <ul className="version-list">
                {document.versions.map((version) => (
                  <li key={String(version.document_id)}>
                    <div>
                      <strong>
                        {version.active
                          ? "Current version"
                          : "Historical version"}
                      </strong>
                      <span>
                        {new Date(String(version.created_at)).toLocaleString()}
                      </span>
                    </div>
                    <a
                      href={`/api/sources/${encodeURIComponent(String(version.document_id))}/file`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Download this version
                    </a>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </details>
  );
}

function DocumentDetails({ document }: { document: SourceDocument }) {
  return (
    <>
      <h3>{document.title || document.filename}</h3>
      <p className="muted source-filename">{document.filename}</p>
      <dl className="source-metadata">
        <div>
          <dt>Author</dt>
          <dd>{document.author || "Not recorded"}</dd>
        </div>
        <div>
          <dt>Attendees</dt>
          <dd>{document.attendees.join(", ") || "Not recorded"}</dd>
        </div>
        <div>
          <dt>Source date</dt>
          <dd>{document.date || "Not recorded"}</dd>
        </div>
        <div>
          <dt>Topic</dt>
          <dd>{document.domain || "Uncategorized"}</dd>
        </div>
        <div>
          <dt>Priority</dt>
          <dd>{document.priority || "Not applicable"}</dd>
        </div>
      </dl>
      {document.warnings?.map((warning, i) => (
        <p className="notice warning" key={i}>
          {warning}
        </p>
      ))}
      {(["decisions", "action_items"] as const).map((key) => (
        <section key={key} className="metadata-section">
          <h4>{key === "decisions" ? "Decisions" : "Action items"}</h4>
          {document[key]?.length ? (
            <ul>
              {document[key].map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">None identified.</p>
          )}
        </section>
      ))}
      <FullDocument documentId={document.document_id} />
      <a
        className="button button-outline"
        href={`/api/sources/${encodeURIComponent(document.document_id)}/file`}
        target="_blank"
        rel="noreferrer"
      >
        Download original
      </a>
    </>
  );
}

type UploadRow = {
  id: number;
  filename: string;
  status: "queued" | "processing" | "ingested" | "unchanged" | "failed";
  warnings: string[];
  error?: string;
};
export function DocumentsView({
  configured,
  onChanged,
}: {
  configured: boolean;
  onChanged: () => void;
}) {
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [samples, setSamples] = useState<UploadSample[]>([]);
  const [sampleError, setSampleError] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [rows, setRows] = useState<UploadRow[]>([]);
  const [selected, setSelected] = useState<SourceDocument | null>(null);
  const [filter, setFilter] = useState("");
  const [dragging, setDragging] = useState(false);
  const sequence = useRef(0);
  const loadingGeneration = useRef(0);
  const sampleGeneration = useRef(0);
  const uploadLock = useRef(false);
  const fileInput = useRef<HTMLInputElement>(null);
  async function load() {
    const generation = ++loadingGeneration.current;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ items: SourceDocument[] }>("/sources");
      if (generation === loadingGeneration.current) {
        setDocuments(result.items);
        setSelected((current) => {
          if (!current) return null;
          const sameVersion = result.items.find(
            (item) => item.document_id === current.document_id,
          );
          if (sameVersion) return sameVersion;
          const replacements = result.items.filter(
            (item) =>
              item.filename === current.filename &&
              item.origin === current.origin,
          );
          return replacements.length === 1 ? replacements[0] : null;
        });
      }
    } catch (e) {
      if (generation === loadingGeneration.current)
        setError((e as Error).message);
    } finally {
      if (generation === loadingGeneration.current) setBusy(false);
    }
  }
  async function loadSamples() {
    const generation = ++sampleGeneration.current;
    try {
      const data = await api<{ items: UploadSample[] }>("/upload-samples");
      if (generation === sampleGeneration.current) {
        setSamples(data.items);
        setSampleError("");
      }
    } catch (e) {
      if (generation === sampleGeneration.current)
        setSampleError((e as Error).message);
    }
  }
  useEffect(() => {
    void load();
    void loadSamples();
  }, []);
  async function upload(files: File[]) {
    if (uploadLock.current || !configured || !files.length) return;
    uploadLock.current = true;
    setUploading(true);
    const queued = files.map((file) => ({ file, id: ++sequence.current }));
    setRows((current) => [
      ...queued.map(({ file, id }) => ({
        id,
        filename: file.name,
        status: "queued" as const,
        warnings: [],
      })),
      ...current,
    ]);
    for (const { file, id } of queued) {
      const update = (patch: Partial<UploadRow>) =>
        setRows((current) =>
          current.map((row) => (row.id === id ? { ...row, ...patch } : row)),
        );
      if (!/\.(md|doc|docx|ppt|pptx|xls|xlsx)$/i.test(file.name)) {
        update({
          status: "failed",
          error:
            "Unsupported format. Choose Markdown, Word, PowerPoint, or Excel.",
        });
        continue;
      }
      if (file.size > 32 * 1024 * 1024) {
        update({
          status: "failed",
          error: "File exceeds the 32 MiB upload limit.",
        });
        continue;
      }
      update({ status: "processing" });
      try {
        const result = await api<{
          filename: string;
          status: "ingested" | "unchanged";
          warnings: string[];
        }>(`/documents/upload?filename=${encodeURIComponent(file.name)}`, {
          method: "POST",
          body: file,
          headers: { "Content-Type": "application/octet-stream" },
        });
        if (!["ingested", "unchanged"].includes(result.status))
          throw new Error(
            "Upload returned an unexpected outcome. Refresh Documents before retrying.",
          );
        update({ status: result.status, warnings: result.warnings || [] });
      } catch (e) {
        update({ status: "failed", error: (e as Error).message });
      }
    }
    uploadLock.current = false;
    setUploading(false);
    await load();
    onChanged();
  }
  const visible = documents.filter((document) =>
    `${document.filename} ${document.title} ${document.author || ""} ${document.domain}`
      .toLowerCase()
      .includes(filter.toLowerCase()),
  );
  return (
    <div className="page-content tools-page">
      <div className="page-heading">
        <div>
          <h1>Documents</h1>
          <p>Sources and their extracted metadata.</p>
        </div>
        <button
          className="button button-outline"
          onClick={() => {
            void load();
            void loadSamples();
          }}
          disabled={busy}
        >
          Refresh
        </button>
      </div>
      <section
        className={`upload-zone ${dragging ? "dragging" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          void upload([...event.dataTransfer.files]);
        }}
      >
        <Upload size={23} />
        <div>
          <h2>Add documents</h2>
          <p>
            Drop files here or choose files. .md, .doc, .docx, .ppt, .pptx,
            .xls, .xlsx · up to 32 MiB per file.
          </p>
        </div>
        <input
          ref={fileInput}
          type="file"
          multiple
          accept=".md,.doc,.docx,.ppt,.pptx,.xls,.xlsx"
          aria-label="Choose documents"
          disabled={!configured || uploading}
          onChange={(event) => {
            void upload([...(event.target.files || [])]);
            event.target.value = "";
          }}
        />
        <button
          className="button button-primary"
          disabled={!configured || uploading}
          onClick={() => fileInput.current?.click()}
        >
          {uploading ? "Processing files…" : "Choose files"}
        </button>
        {!configured && (
          <p className="notice warning">
            Configure OPENROUTER_API_KEY on the server before uploading.
          </p>
        )}
      </section>
      {rows.length > 0 && (
        <section
          className="upload-results"
          aria-label="Upload outcomes"
          aria-live="polite"
        >
          {rows.map((row) => (
            <div className="upload-outcome" key={row.id}>
              <strong>{row.filename}</strong>
              <span
                className={`kind-tag ${row.status === "failed" ? "rejected" : ""}`}
              >
                {row.status === "processing" ? (
                  <>
                    <LoaderCircle size={14} className="spin" /> Uploading and
                    processing
                  </>
                ) : row.status === "ingested" ? (
                  "Indexed"
                ) : row.status === "unchanged" ? (
                  "Unchanged"
                ) : row.status === "queued" ? (
                  "Queued"
                ) : (
                  "Failed"
                )}
              </span>
              {row.error && <p role="alert">{row.error}</p>}
              {row.warnings.map((warning, i) => (
                <p key={i}>{warning}</p>
              ))}
            </div>
          ))}
        </section>
      )}
      <details className="sample-imports" open>
        <summary>Two sample transcripts to try</summary>
        <p className="muted">
          These files are available to download but are not included in the
          initial 24-document index. Download one, then add it above.
        </p>
        {sampleError && <p role="alert">{sampleError}</p>}
        <div className="sample-grid">
          {samples.map((sample) => (
            <article key={sample.id}>
              <h3>{sample.title}</h3>
              <p>{sample.description}</p>
              <p>
                <strong>Before / after upload:</strong>{" "}
                {sample.after_question || sample.before_question}
              </p>
              <a
                href={sample.download_url}
                target="_blank"
                rel="noreferrer"
                className="text-button"
              >
                Download {sample.filename}
              </a>
            </article>
          ))}
        </div>
      </details>
      <div className="document-toolbar">
        <label htmlFor="document-filter">Find a document</label>
        <input
          id="document-filter"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Filename, author, or topic"
        />
        <span>{documents.length} indexed documents</span>
      </div>
      {error && (
        <p role="alert" className="notice error">
          {error}
        </p>
      )}
      {busy && !documents.length ? (
        <p role="status">Loading documents…</p>
      ) : !visible.length ? (
        <p className="empty-state">
          {filter
            ? "No documents match this filter."
            : error
              ? "Documents could not be loaded. Try Refresh."
              : "No documents indexed yet. Add a file to start."}
        </p>
      ) : (
        <div className="document-list">
          {visible.map((document) => (
            <button
              key={document.document_id}
              className="document-row"
              onClick={() => setSelected(document)}
            >
              <FileText size={20} />
              <div>
                <strong>{document.filename}</strong>
                <span>
                  {document.author
                    ? `By ${document.author}`
                    : document.attendees.length
                      ? `Attendees: ${document.attendees.join(", ")}`
                      : "Attribution not recorded"}{" "}
                  · {document.date || "Date not recorded"}
                </span>
                <span>
                  {document.domain || "Uncategorized"}
                  {document.priority ? ` · ${document.priority} priority` : ""}
                </span>
              </div>
              <span className="document-state">
                {document.warnings?.length
                  ? `${document.warnings.length} notice${document.warnings.length === 1 ? "" : "s"}`
                  : "Indexed"}
                <small>
                  {document.chunk_count} passages ·{" "}
                  {document.origin === "uploaded" ? "Uploaded" : "Corpus"}
                </small>
              </span>
            </button>
          ))}
        </div>
      )}
      {selected && (
        <Modal title="Document details" wide onClose={() => setSelected(null)}>
          <DocumentDetails document={selected} />
        </Modal>
      )}
    </div>
  );
}

export function AboutView() {
  return (
    <div className="page-content about-page">
      <h1>About this workspace</h1>
      <p>
        Relay is an internal knowledge workspace for a fictional AI deployment
        consultancy. Ask one question at a time, inspect its source evidence,
        and route gaps to people named in relevant documents.
      </p>
      <h2>Initial client engagements</h2>
      <dl className="engagements">
        <div>
          <dt>Atlas Forge</dt>
          <dd>
            A manufacturing knowledge assistant: release gates, rollout
            planning, logging, and security.
          </dd>
        </div>
        <div>
          <dt>Beacon Route</dt>
          <dd>
            A logistics forecasting pilot: data quality, acceptance thresholds,
            commercial terms, and vendor agreements.
          </dd>
        </div>
        <div>
          <dt>Cedar Vale</dt>
          <dd>
            A clinic policy assistant: access controls, privacy, evaluation, and
            incident rehearsals.
          </dd>
        </div>
      </dl>
      <h2>What is included</h2>
      <p>
        The initial corpus contains 24 fictional documents: 12 meeting
        transcripts and 12 Word, PowerPoint, and Excel files, including legacy
        formats. Dates, owners, conflicting decisions, and unanswered questions
        are intentional. Two optional upload samples introduce a fourth
        engagement, Juniper Harbor; they are not part of the initial index.
      </p>
      <h2>How to use it</h2>
      <p>
        Ask returns an independent answer, not a continuing conversation.
        Documents shows sources and lets you add files. Review queue preserves
        unanswered questions and rejected or corrected answers. Outbox saves
        simulated handoffs; no email is delivered.
      </p>
      <h2>Readiness and evaluation</h2>
      <p>
        Document extraction and indexing are automated. Source notices identify
        specific problems such as missing attribution or conversion limits.
        Answer-evaluation findings concern the quality of generated answers;
        they do not require human approval of every document. Corrections and
        review notes never silently change the source documents.
      </p>
      <p>
        <a href="/docs" target="_blank" rel="noreferrer">
          Open API reference
        </a>
      </p>
    </div>
  );
}

export function DeveloperView({
  ready,
  onChanged,
}: {
  ready: boolean;
  onChanged: () => void;
}) {
  const [mode, setMode] = useState<"search" | "query">("search");
  const [question, setQuestion] = useState(
    "What is Atlas Forge's current launch date?",
  );
  const [shell, setShell] = useState("posix");
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const payload = JSON.stringify({ question: question.trim() });
  const endpoint = `/api/${mode}`;
  const quote = (value: string) => `'${value.replaceAll("'", "'\\''")}'`;
  const command =
    shell === "posix"
      ? `curl ${quote(`${location.origin}${endpoint}`)} -H 'Content-Type: application/json' --data-raw ${quote(payload)}`
      : `$body = '${payload.replaceAll("'", "''")}'; Invoke-RestMethod -Method Post -Uri '${location.origin}${endpoint}' -ContentType 'application/json' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))`;
  async function execute() {
    if (busy || !ready || question.trim().length < 3) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await post<unknown>(`/${mode}`, { question: question.trim() }));
      if (mode === "query") onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page-content developer-page">
      <div className="page-heading">
        <div>
          <h1>Developer tools</h1>
          <p>Inspect the local API. Requests run against this workspace.</p>
        </div>
        <a href="/docs" target="_blank" rel="noreferrer">
          API reference
        </a>
      </div>
      <form
        className="surface developer-form"
        onSubmit={(event) => {
          event.preventDefault();
          void execute();
        }}
      >
        <label>
          API operation
          <select
            value={mode}
            disabled={busy}
            onChange={(event) => {
              setMode(event.target.value as "search" | "query");
              setCopied(false);
              setResult(null);
              setError("");
            }}
          >
            <option value="search">Search only — candidate evidence</option>
            <option value="query">
              Answer API — supported claims and routing
            </option>
          </select>
        </label>
        <p className="muted">
          {mode === "search"
            ? "Search returns candidate passages. It does not generate an answer or save a query or knowledge gap."
            : "Answer runs the complete pipeline and saves a query. Missing information may create a review item."}
        </p>
        <label htmlFor="developer-question">API question</label>
        <textarea
          id="developer-question"
          value={question}
          disabled={busy}
          maxLength={3000}
          onChange={(event) => {
            setQuestion(event.target.value);
            setCopied(false);
          }}
          rows={3}
        />
        <button
          className="button button-primary"
          disabled={busy || !ready || question.trim().length < 3}
        >
          {busy ? "Running request…" : "Run request"}
        </button>
        {!ready && (
          <p className="notice warning">
            The service must be ready before running a request.
          </p>
        )}
      </form>
      <section className="surface command-panel">
        <div className="section-heading">
          <h2>Reproduce this request</h2>
          <label>
            Command format
            <select
              value={shell}
              onChange={(event) => {
                setShell(event.target.value);
                setCopied(false);
              }}
            >
              <option value="posix">POSIX curl</option>
              <option value="powershell">PowerShell</option>
            </select>
          </label>
          <button
            className="button button-outline"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(command);
                setCopied(true);
              } catch {
                setError(
                  "Clipboard unavailable. Select and copy the command below.",
                );
              }
            }}
          >
            {copied ? <Check size={15} /> : <Copy size={15} />}
            {copied ? "Copied" : "Copy command"}
          </button>
        </div>
        <pre>{command}</pre>
      </section>
      {error && (
        <p role="alert" className="notice error">
          {error}
        </p>
      )}
      <section className="surface">
        <h2>JSON response</h2>
        {busy ? (
          <p role="status">Waiting for the API…</p>
        ) : result ? (
          <pre aria-label="JSON response">
            {JSON.stringify(result, null, 2)}
          </pre>
        ) : (
          <p className="muted">Run a request to inspect its response.</p>
        )}
      </section>
    </div>
  );
}
