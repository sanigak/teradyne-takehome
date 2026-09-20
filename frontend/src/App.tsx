import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  FileText,
  FolderOpen,
  Inbox,
  Layers3,
  LoaderCircle,
  MessageSquareText,
  PanelRightClose,
  PencilLine,
  Plus,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";
import { api, post } from "./api";
import type {
  Evidence,
  Health,
  OutboxItem,
  Quality,
  QueryResult,
  ReviewItem,
} from "./api";

type View = "ask" | "review" | "outbox";
type EvidenceSelection = { evidence: Evidence; quote?: string };
const viewTitles: Record<View, string> = {
  ask: "Ask the workspace",
  review: "Review queue",
  outbox: "Outbox",
};
const samples = [
  {
    label: "Find a decision",
    question:
      "What is Atlas Forge’s current launch date, and what changed from kickoff?",
    icon: Layers3,
  },
  {
    label: "Trace an action",
    question:
      "Who owns Cedar Vale incident containment and client communication?",
    icon: CheckCheck,
  },
  {
    label: "Surface a gap",
    question:
      "What is the weather vendor’s signed deletion SLA for Beacon Route?",
    icon: MessageSquareText,
  },
];

function formatDate(date: string | null) {
  if (!date) return "Date not recorded";
  const parsed = new Date(date.length === 10 ? `${date}T12:00:00` : date);
  return Number.isNaN(parsed.getTime())
    ? date
    : parsed.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
}

function ErrorNotice({
  children,
  onClose,
}: {
  children: ReactNode;
  onClose?: () => void;
}) {
  return (
    <div className="notice error" role="alert">
      <CircleAlert size={18} />
      <span>{children}</span>
      {onClose && (
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Dismiss error"
        >
          <X size={16} />
        </button>
      )}
    </div>
  );
}

function EmptyState({
  icon,
  title,
  children,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

function StatusPill({ status }: { status: QueryResult["status"] }) {
  return (
    <span className={`status-pill ${status}`}>
      {status === "answered" ? (
        <ShieldCheck size={13} />
      ) : (
        <CircleAlert size={13} />
      )}
      {status === "answered"
        ? "Source-grounded answer"
        : status === "partial"
          ? "Partial answer"
          : "More context needed"}
    </span>
  );
}

function AnswerClaims({
  result,
  onEvidence,
}: {
  result: QueryResult;
  onEvidence: (e: EvidenceSelection) => void;
}) {
  return (
    <div className="answer-claims">
      {result.claims.map((claim, index) => (
        <div className="claim" key={index}>
          <span className="claim-index">
            {String(index + 1).padStart(2, "0")}
          </span>
          <div>
            <p>{claim.text}</p>
            <div className="citation-row">
              {claim.citations.map((citation, i) => {
                const source = result.evidence.find(
                  (e) => e.chunk_id === citation.chunk_id,
                );
                const number =
                  result.evidence.findIndex(
                    (e) => e.chunk_id === citation.chunk_id,
                  ) + 1;
                return source ? (
                  <button
                    className="citation citation-attributed"
                    key={`${citation.chunk_id}-${i}`}
                    onClick={() =>
                      onEvidence({ evidence: source, quote: citation.quote })
                    }
                    title={`${source.filename} · ${source.locator}`}
                  >
                    <FileText size={12} />
                    <span className="citation-label">
                      <strong>
                        {number}. {source.filename}
                      </strong>
                      <small>
                        {source.author
                          ? `By ${source.author}`
                          : source.attendees.length > 0
                            ? `Attendees: ${source.attendees.join(", ")}`
                            : "Attribution not recorded"}
                      </small>
                    </span>
                    <ArrowUpRight size={11} />
                  </button>
                ) : null;
              })}
            </div>
          </div>
        </div>
      ))}
      {result.message && (
        <div
          className={`answer-note ${result.status === "answered" ? "subtle" : ""}`}
        >
          <BookOpen size={16} />
          <p>{result.message}</p>
        </div>
      )}
    </div>
  );
}

function EvidencePanel({
  selection,
  evidence,
  onSelect,
  onClose,
}: {
  selection: EvidenceSelection | null;
  evidence: Evidence[];
  onSelect: (e: EvidenceSelection) => void;
  onClose: () => void;
}) {
  if (!selection)
    return (
      <aside className="evidence-panel placeholder-panel">
        <div className="panel-heading">
          <BookOpen size={17} />
          <h3>Evidence, in context</h3>
        </div>
        <div className="evidence-empty-art">
          <div className="paper paper-back" />
          <div className="paper paper-front">
            <span />
            <span />
            <span />
            <div>
              <ShieldCheck size={22} />
            </div>
            <span />
          </div>
          <div className="art-orbit" />
        </div>
        <h3>Every answer has a paper trail.</h3>
        <p>
          Ask a question to see the original source, who contributed, and the
          exact passage behind each answer.
        </p>
        <div className="evidence-principles">
          <div>
            <Check size={14} /> Original documents, preserved
          </div>
          <div>
            <Check size={14} /> Citations you can inspect
          </div>
          <div>
            <Check size={14} /> Clear when context is missing
          </div>
        </div>
      </aside>
    );
  const e = selection.evidence;
  return (
    <aside className="evidence-panel" aria-label="Source evidence">
      <div className="panel-heading">
        <BookOpen size={17} />
        <h3>Source evidence</h3>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close evidence"
        >
          <PanelRightClose size={17} />
        </button>
      </div>
      {evidence.length > 1 && (
        <div className="source-select">
          <label htmlFor="source-select">Retrieved sources</label>
          <div>
            <select
              id="source-select"
              value={e.chunk_id}
              onChange={(event) => {
                const found = evidence.find(
                  (item) => item.chunk_id === event.target.value,
                );
                if (found) onSelect({ evidence: found });
              }}
            >
              {evidence.map((item, i) => (
                <option key={item.chunk_id} value={item.chunk_id}>
                  {i + 1}. {item.filename} · {item.locator}
                </option>
              ))}
            </select>
            <ChevronDown size={14} />
          </div>
        </div>
      )}
      <div className="source-body">
        <span className="file-type">
          {e.filename.split(".").pop()?.toUpperCase()} DOCUMENT
        </span>
        <h3>{e.title || e.filename}</h3>
        <p className="source-filename">{e.filename}</p>
        <div className="source-tags">
          <span>{e.domain || "Uncategorized"}</span>
          {e.priority && (
            <span className="priority-tag">{e.priority} priority</span>
          )}
        </div>
        <dl className="source-metadata">
          <div>
            <dt>Author</dt>
            <dd>{e.author || "Not recorded"}</dd>
          </div>
          {e.attendees.length > 0 && (
            <div>
              <dt>Attendees</dt>
              <dd>{e.attendees.join(", ")}</dd>
            </div>
          )}
          <div>
            <dt>Source date</dt>
            <dd>{formatDate(e.date)}</dd>
          </div>
          <div>
            <dt>Location</dt>
            <dd>{e.locator}</dd>
          </div>
        </dl>
        <div className="source-excerpt">
          <div className="eyebrow">
            <span className="tiny-line" />
            {selection.quote ? "Cited passage" : "Source passage"}
          </div>
          <blockquote>{selection.quote || e.text}</blockquote>
        </div>
        {selection.quote && selection.quote !== e.text && (
          <details className="full-context">
            <summary>
              View surrounding context <ChevronDown size={13} />
            </summary>
            <p>{e.text}</p>
          </details>
        )}
        <a
          className="button button-outline download"
          href={`/api/sources/${encodeURIComponent(e.document_id)}/file`}
          target="_blank"
          rel="noreferrer"
        >
          <ArrowDownToLine size={15} /> Download original
          <ArrowUpRight size={13} />
        </a>
        <p className="source-footnote">
          <ShieldCheck size={13} /> Preserved source version used for this
          answer.
        </p>
      </div>
    </aside>
  );
}

function Feedback({
  result,
  onSaved,
}: {
  result: QueryResult;
  onSaved: () => void;
}) {
  const [kind, setKind] = useState<"rejected" | "corrected" | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  async function submit(chosen: "accepted" | "rejected" | "corrected") {
    setBusy(true);
    setError("");
    try {
      await post("/feedback", {
        query_id: result.query_id,
        kind: chosen,
        comment,
      });
      setSaved(
        chosen === "accepted"
          ? "Thanks. Your feedback has been recorded."
          : "Added to the review queue for a team lead.",
      );
      setKind(null);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (saved)
    return (
      <div className="feedback-saved" role="status">
        <CircleCheck size={16} />
        {saved}
      </div>
    );
  return (
    <div className="feedback">
      <div className="feedback-top">
        <span>Did this answer help?</span>
        <div>
          <button
            disabled={busy}
            className="text-button"
            onClick={() => submit("accepted")}
          >
            <ThumbsUp size={14} /> Yes
          </button>
          <button
            disabled={busy}
            className={`text-button ${kind === "rejected" ? "selected" : ""}`}
            onClick={() => setKind("rejected")}
          >
            <ThumbsDown size={14} /> Not quite
          </button>
          <button
            disabled={busy}
            className={`text-button ${kind === "corrected" ? "selected" : ""}`}
            onClick={() => setKind("corrected")}
          >
            <PencilLine size={14} /> Correct
          </button>
        </div>
      </div>
      {kind && (
        <form
          className="feedback-form"
          onSubmit={(event) => {
            event.preventDefault();
            void submit(kind);
          }}
        >
          <label htmlFor="feedback-comment">
            {kind === "corrected"
              ? "What should the answer say?"
              : "What is missing or incorrect?"}
          </label>
          <textarea
            id="feedback-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Give the review team enough context to investigate…"
            required
            maxLength={10000}
            rows={3}
          />
          <p>Feedback is reviewed separately; original sources stay intact.</p>
          <div className="form-actions">
            <button
              type="button"
              className="button button-ghost"
              onClick={() => setKind(null)}
            >
              Cancel
            </button>
            <button
              className="button button-primary button-small"
              disabled={busy || !comment.trim()}
            >
              {busy ? (
                <LoaderCircle className="spin" size={14} />
              ) : (
                <Check size={14} />
              )}
              Submit {kind === "corrected" ? "correction" : "feedback"}
            </button>
          </div>
        </form>
      )}
      {error && <ErrorNotice>{error}</ErrorNotice>}
    </div>
  );
}

function RoutingDraft({
  result,
  onSaved,
  onEvidence,
}: {
  result: QueryResult;
  onSaved: () => void;
  onEvidence: (e: EvidenceSelection) => void;
}) {
  const [index, setIndex] = useState(0);
  const route = result.routing[index];
  const [recipient, setRecipient] = useState(route?.recipient || "");
  const [subject, setSubject] = useState(
    `Clarification: ${result.question.slice(0, 160)}`,
  );
  const [body, setBody] = useState(route?.draft_question || result.question);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  if (!route)
    return (
      <div className="no-expert">
        <CircleAlert size={17} />
        <div>
          <strong>No supported contact found</strong>
          <p>
            The available sources do not identify a relevant author or attendee.
            This question is saved in the review queue.
          </p>
        </div>
      </div>
    );
  async function send(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await post("/outbox", {
        query_id: result.query_id,
        recipient: recipient.trim(),
        subject: subject.trim(),
        body: body.trim(),
        evidence_ids: route.evidence_ids,
      });
      setSaved(true);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="routing-card">
      <div className="section-label">
        <span className="icon-circle">
          <Send size={16} />
        </span>
        <div>
          <h3>Take the question to the right person</h3>
          <p>A suggested handoff, based on your sources.</p>
        </div>
      </div>
      {saved ? (
        <div className="notice success" role="status">
          <CircleCheck size={18} />
          <span>
            Draft saved to Outbox as a simulated send. No email was delivered.
          </span>
        </div>
      ) : (
        <>
          {result.routing.length > 1 && (
            <label className="route-choice">
              Suggested contact
              <select
                value={index}
                onChange={(e) => {
                  const i = Number(e.target.value);
                  setIndex(i);
                  setRecipient(result.routing[i].recipient);
                  setBody(result.routing[i].draft_question);
                }}
              >
                {result.routing.map((item, i) => (
                  <option key={`${item.recipient}-${i}`} value={i}>
                    {item.recipient}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="routing-reason">
            <span className="eyebrow">Why this person</span>
            <p>{route.reason}</p>
            <div className="citation-row">
              {route.evidence_ids.map((id) => {
                const e = result.evidence.find((item) => item.chunk_id === id);
                return e ? (
                  <button
                    className="citation"
                    key={id}
                    onClick={() => onEvidence({ evidence: e })}
                  >
                    <FileText size={12} />
                    {e.filename}
                    <ArrowUpRight size={11} />
                  </button>
                ) : null;
              })}
            </div>
          </div>
          <form className="draft-form" onSubmit={send}>
            <label>
              To
              <input
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
                required
                maxLength={500}
              />
            </label>
            <label>
              Subject
              <input
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                required
                maxLength={500}
              />
            </label>
            <label>
              Message
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                required
                maxLength={10000}
                rows={5}
              />
            </label>
            <div className="draft-footer">
              <span>
                <ShieldCheck size={14} /> Simulation only. No email is sent.
              </span>
              <button
                className="button button-primary button-small"
                disabled={
                  busy || !recipient.trim() || !subject.trim() || !body.trim()
                }
              >
                {busy ? (
                  <LoaderCircle size={15} className="spin" />
                ) : (
                  <Send size={15} />
                )}
                Simulate send
              </button>
            </div>
          </form>
          {error && <ErrorNotice>{error}</ErrorNotice>}
        </>
      )}
    </section>
  );
}

function ReviewView({
  items,
  loading,
  error,
  reload,
  onEvidence,
  selectedId,
  setSelectedId,
}: {
  items: ReviewItem[];
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
  onEvidence: (e: EvidenceSelection, all: Evidence[]) => void;
  selectedId: string | null;
  setSelectedId: (id: string | null) => void;
}) {
  const [filter, setFilter] = useState<"open" | "resolved" | "all">("open");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState("");
  const filtered = items.filter(
    (item) => filter === "all" || item.status === filter,
  );
  const selected = items.find((item) => item.id === selectedId);
  async function resolve() {
    if (!selected) return;
    setBusy(true);
    setLocalError("");
    try {
      await api(`/review/${encodeURIComponent(selected.id)}`, {
        method: "PATCH",
        body: JSON.stringify({
          status: selected.status === "open" ? "resolved" : "open",
          resolution_note: note.trim(),
        }),
      });
      await reload();
    } catch (e) {
      setLocalError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page-content">
      <div className="page-heading">
        <div>
          <span className="eyebrow">Human judgment, in the loop</span>
          <h1>
            Review queue<span className="heading-period">.</span>
          </h1>
          <p>Close knowledge gaps and turn feedback into better answers.</p>
        </div>
        <button
          className="button button-outline"
          onClick={() => void reload()}
          disabled={loading}
        >
          <RefreshCw size={15} className={loading ? "spin" : ""} />
          Refresh
        </button>
      </div>
      {error && <ErrorNotice>{error}</ErrorNotice>}
      <div className="queue-toolbar">
        <div className="segmented" aria-label="Filter reviews">
          {(["open", "resolved", "all"] as const).map((value) => (
            <button
              key={value}
              className={filter === value ? "active" : ""}
              onClick={() => setFilter(value)}
            >
              {value === "all"
                ? "All items"
                : value === "open"
                  ? "Open"
                  : "Resolved"}
              <span>
                {
                  items.filter(
                    (item) => value === "all" || item.status === value,
                  ).length
                }
              </span>
            </button>
          ))}
        </div>
        <span className="muted small">Original answers are preserved</span>
      </div>
      <div className={`review-layout ${selected ? "has-selection" : ""}`}>
        <div className="review-list">
          {loading && items.length === 0 ? (
            <div className="loading-state">
              <LoaderCircle className="spin" size={20} />
              Loading review items…
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<CheckCheck size={29} />}
              title={
                filter === "resolved"
                  ? "No resolved items yet"
                  : "You’re all caught up"
              }
            >
              {filter === "resolved"
                ? "Items you resolve will appear here with their resolution notes."
                : "Unanswered questions and rejected or corrected answers appear here for review."}
            </EmptyState>
          ) : (
            filtered.map((item) => (
              <button
                key={item.id}
                className={`review-row ${selected?.id === item.id ? "active" : ""}`}
                onClick={() => {
                  setSelectedId(item.id);
                  setNote(item.resolution_note || "");
                  setLocalError("");
                }}
              >
                <div className="review-row-top">
                  <span className={`kind-tag ${item.kind}`}>
                    {item.kind === "gap"
                      ? "Knowledge gap"
                      : item.kind === "corrected"
                        ? "Correction"
                        : "Rejected answer"}
                  </span>
                  <span>{formatDate(item.created_at)}</span>
                </div>
                <h3>{item.question}</h3>
                <p>
                  {item.comment ||
                    item.answer?.message ||
                    "Additional source context is needed."}
                </p>
                <div className="review-row-bottom">
                  <span className={`review-status ${item.status}`}>
                    <span />
                    {item.status === "open" ? "Needs review" : "Resolved"}
                  </span>
                  <ChevronRight size={16} />
                </div>
              </button>
            ))
          )}
        </div>
        {selected && (
          <section className="review-detail">
            <div className="detail-heading">
              <span className="eyebrow">Review detail</span>
              <button
                className="icon-button"
                onClick={() => setSelectedId(null)}
                aria-label="Close review"
              >
                <X size={17} />
              </button>
            </div>
            <h2>{selected.question}</h2>
            <div className="review-detail-meta">
              <span className={`kind-tag ${selected.kind}`}>
                {selected.kind === "gap"
                  ? "Knowledge gap"
                  : selected.kind === "corrected"
                    ? "Correction"
                    : "Rejected answer"}
              </span>
              <span>{formatDate(selected.created_at)}</span>
            </div>
            {selected.comment && (
              <div className="review-comment">
                <span className="eyebrow">Submitted feedback</span>
                <p>{selected.comment}</p>
              </div>
            )}
            <div className="snapshot-heading">
              <span className="eyebrow">Original answer snapshot</span>
              <StatusPill status={selected.answer.status} />
            </div>
            <AnswerClaims
              result={selected.answer}
              onEvidence={(e) => onEvidence(e, selected.answer.evidence)}
            />
            {selected.answer.evidence.length > 0 && (
              <details className="review-sources">
                <summary>
                  All retrieved evidence ({selected.answer.evidence.length})
                </summary>
                <div className="citation-row">
                  {selected.answer.evidence.map((e) => (
                    <button
                      key={e.chunk_id}
                      className="citation"
                      onClick={() =>
                        onEvidence({ evidence: e }, selected.answer.evidence)
                      }
                    >
                      <FileText size={12} />
                      {e.filename}
                      <ArrowUpRight size={11} />
                    </button>
                  ))}
                </div>
              </details>
            )}
            <div className="resolution-form">
              <label htmlFor="resolution-note">Resolution note</label>
              <textarea
                id="resolution-note"
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="What was checked or clarified? Link follow-up work if needed."
                maxLength={10000}
                disabled={busy}
              />
              <p>
                Resolving an item records your decision. It does not modify
                source documents.
              </p>
              <button
                className="button button-primary"
                disabled={busy || (selected.status === "open" && !note.trim())}
                onClick={() => void resolve()}
              >
                {busy ? (
                  <LoaderCircle size={15} className="spin" />
                ) : (
                  <Check size={15} />
                )}
                {selected.status === "open" ? "Resolve item" : "Reopen item"}
              </button>
              {localError && <ErrorNotice>{localError}</ErrorNotice>}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

function OutboxView({
  items,
  error,
  loading,
  reload,
  openQuery,
}: {
  items: OutboxItem[];
  error: string;
  loading: boolean;
  reload: () => Promise<void>;
  openQuery: (id: string) => Promise<void>;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = items.find((item) => item.id === selectedId) || items[0];
  return (
    <div className="page-content">
      <div className="page-heading">
        <div>
          <span className="eyebrow">Keep the conversation moving</span>
          <h1>
            Outbox<span className="heading-period">.</span>
          </h1>
          <p>Your saved handoffs, with the evidence that started them.</p>
        </div>
        <button
          className="button button-outline"
          disabled={loading}
          onClick={() => void reload()}
        >
          <RefreshCw size={15} className={loading ? "spin" : ""} />
          Refresh
        </button>
      </div>
      <div className="notice neutral">
        <ShieldCheck size={18} />
        <span>
          <strong>This is a simulated outbox.</strong> Messages are saved
          locally. No email is sent.
        </span>
      </div>
      {error && <ErrorNotice>{error}</ErrorNotice>}
      {loading && items.length === 0 ? (
        <div className="loading-state">
          <LoaderCircle size={20} className="spin" />
          Loading outbox…
        </div>
      ) : items.length === 0 ? (
        <div className="surface">
          <EmptyState
            icon={<Send size={29} />}
            title="A place for your next question"
          >
            When an answer needs a little more context, edit a suggested handoff
            and simulate sending it. You’ll find it here.
          </EmptyState>
        </div>
      ) : (
        <div className="outbox-layout">
          <div className="outbox-list">
            {items.map((item) => (
              <button
                className={`outbox-row ${selected?.id === item.id ? "active" : ""}`}
                key={item.id}
                onClick={() => setSelectedId(item.id)}
              >
                <div className="outbox-row-top">
                  <span className="avatar">
                    {item.recipient.trim().slice(0, 1).toUpperCase()}
                  </span>
                  <strong>{item.recipient}</strong>
                  <ArrowUpRight size={14} />
                </div>
                <h3>{item.subject}</h3>
                <p>{item.body}</p>
                <div>
                  <span className="kind-tag simulated">Simulated</span>
                  <span className="small muted">
                    {formatDate(item.created_at)}
                  </span>
                </div>
              </button>
            ))}
          </div>
          {selected && (
            <article className="outbox-detail">
              <div className="detail-heading">
                <span className="eyebrow">Saved message</span>
                <span className="kind-tag simulated">
                  <Check size={12} />
                  Simulated send
                </span>
              </div>
              <h2>{selected.subject}</h2>
              <dl className="message-meta">
                <div>
                  <dt>To</dt>
                  <dd>{selected.recipient}</dd>
                </div>
                <div>
                  <dt>Saved</dt>
                  <dd>{formatDate(selected.created_at)}</dd>
                </div>
              </dl>
              <div className="message-body">{selected.body}</div>
              <div className="message-footer">
                <span>
                  {selected.evidence_ids.length} supporting passage
                  {selected.evidence_ids.length === 1 ? "" : "s"}
                </span>
                <button
                  className="text-button"
                  onClick={() => void openQuery(selected.query_id)}
                >
                  View original question <ArrowUpRight size={14} />
                </button>
              </div>
            </article>
          )}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [view, setView] = useState<View>("ask");
  const [health, setHealth] = useState<Health | null>(null);
  const [quality, setQuality] = useState<Quality | null>(null);
  const [healthError, setHealthError] = useState("");
  const [reviewItems, setReviewItems] = useState<ReviewItem[]>([]);
  const [outboxItems, setOutboxItems] = useState<OutboxItem[]>([]);
  const [reviewError, setReviewError] = useState("");
  const [outboxError, setOutboxError] = useState("");
  const [reviewLoading, setReviewLoading] = useState(false);
  const [outboxLoading, setOutboxLoading] = useState(false);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [selection, setSelection] = useState<EvidenceSelection | null>(null);
  const [drawerEvidence, setDrawerEvidence] = useState<Evidence[]>([]);
  const [reviewEvidence, setReviewEvidence] =
    useState<EvidenceSelection | null>(null);
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [queryError, setQueryError] = useState("");
  const [showStatus, setShowStatus] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  async function loadStatus() {
    const [h, q] = await Promise.allSettled([
      api<Health>("/health"),
      api<Quality>("/quality"),
    ]);
    if (h.status === "fulfilled") {
      setHealth(h.value);
      setHealthError("");
    } else setHealthError((h.reason as Error).message);
    if (q.status === "fulfilled") setQuality(q.value);
  }
  async function loadReviews() {
    setReviewLoading(true);
    try {
      const data = await api<{ items: ReviewItem[] }>("/review");
      setReviewItems(data.items);
      setReviewError("");
    } catch (e) {
      setReviewError((e as Error).message);
    } finally {
      setReviewLoading(false);
    }
  }
  async function loadOutbox() {
    setOutboxLoading(true);
    try {
      const data = await api<{ items: OutboxItem[] }>("/outbox");
      setOutboxItems(data.items);
      setOutboxError("");
    } catch (e) {
      setOutboxError((e as Error).message);
    } finally {
      setOutboxLoading(false);
    }
  }
  useEffect(() => {
    void loadStatus();
    void loadReviews();
    void loadOutbox();
  }, []);
  useEffect(() => {
    if (!reviewEvidence && !showStatus) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]');
    const focusable = () => [
      ...(dialog?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), a[href], input, select, textarea, summary, [tabindex="0"]',
      ) || []),
    ];
    focusable()[0]?.focus();
    const listener = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setReviewEvidence(null);
        setShowStatus(false);
      }
      if (event.key === "Tab") {
        const elements = focusable();
        const first = elements[0];
        const last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    window.addEventListener("keydown", listener);
    return () => {
      window.removeEventListener("keydown", listener);
      previous?.focus();
    };
  }, [reviewEvidence, showStatus]);
  async function ask(event: FormEvent) {
    event.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setQueryError("");
    setResult(null);
    setSelection(null);
    try {
      const answer = await post<QueryResult>("/query", {
        question: question.trim(),
      });
      setResult(answer);
      const firstId = answer.claims[0]?.citations[0]?.chunk_id;
      const first =
        answer.evidence.find((e) => e.chunk_id === firstId) ||
        answer.evidence[0];
      if (first)
        setSelection({
          evidence: first,
          quote: answer.claims[0]?.citations[0]?.quote,
        });
      void loadReviews();
      void loadStatus();
    } catch (e) {
      setQueryError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  async function openQuery(id: string) {
    setLoading(true);
    setQueryError("");
    setView("ask");
    setResult(null);
    setSelection(null);
    try {
      const answer = await api<QueryResult>(`/query/${encodeURIComponent(id)}`);
      setResult(answer);
      setQuestion(answer.question);
      if (answer.evidence[0]) setSelection({ evidence: answer.evidence[0] });
    } catch (e) {
      setQueryError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  const pending = reviewItems.filter((item) => item.status === "open").length;
  const statusText = healthError
    ? "Server unavailable"
    : !health
      ? "Connecting…"
      : !health.configured
        ? "Setup needed"
        : !health.ready
          ? "Ingestion needed"
          : "Workspace ready";
  const displayWarning = health && !health.ready;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button
          className="brand"
          onClick={() => setView("ask")}
          aria-label="Relay AI home"
        >
          <span className="brand-mark">
            <span />
            <span />
            <span />
          </span>
          <span>
            relay<span className="brand-ai">ai</span>
          </span>
        </button>
        <div className="workspace-label">
          <span className="workspace-monogram">R</span>
          <div>
            <strong>Delivery workspace</strong>
            <span>Internal knowledge</span>
          </div>
          <span className="workspace-dot" />
        </div>
        <div className="nav-caption">Workspace</div>
        <nav aria-label="Main navigation">
          {(
            [
              { id: "ask", label: "Ask the workspace", icon: Search },
              { id: "review", label: "Review queue", icon: Inbox },
              { id: "outbox", label: "Outbox", icon: Send },
            ] as const
          ).map((item) => (
            <button
              key={item.id}
              className={`nav-item ${view === item.id ? "active" : ""}`}
              onClick={() => {
                setView(item.id);
                if (item.id === "review") void loadReviews();
                if (item.id === "outbox") void loadOutbox();
              }}
            >
              <item.icon size={18} strokeWidth={1.7} />
              <span>{item.label}</span>
              {item.id === "review" && pending > 0 && (
                <span className="nav-count">{pending}</span>
              )}
              {item.id === "outbox" && outboxItems.length > 0 && (
                <span className="nav-count">{outboxItems.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="note-spark">
            <Sparkles size={18} />
          </span>
          <h3>
            A little less searching.
            <br />A lot more knowing.
          </h3>
          <p>Your team’s knowledge, connected to the work ahead.</p>
          <span className="note-rule" />
        </div>
        <button className="sidebar-status" onClick={() => setShowStatus(true)}>
          <span
            className={`status-dot ${health?.ready && !healthError ? "ready" : "warning"}`}
          />
          <span>{statusText}</span>
          <ChevronRight size={14} />
        </button>
        <div className="sidebar-footer">
          <span className="avatar user-avatar">DT</span>
          <div>
            <strong>Delivery team</strong>
            <span>Local workspace</span>
          </div>
        </div>
      </aside>
      <main className="main-content">
        <header className="topbar">
          <div>
            <FolderOpen size={15} />
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{viewTitles[view]}</strong>
          </div>
          <button className="status-top" onClick={() => setShowStatus(true)}>
            <span
              className={`status-dot ${health?.ready && !healthError ? "ready" : "warning"}`}
            />
            {statusText}
            <ChevronDown size={12} />
          </button>
        </header>
        {view === "ask" ? (
          <div className="page-content ask-page">
            <div className="ask-heading">
              <span className="eyebrow">
                <span className="tiny-line" />
                Your collective know-how
              </span>
              <h1>
                Good answers start with
                <br />
                the right <em>evidence.</em>
              </h1>
              <p>Turn your team’s documents into answers you can trace.</p>
            </div>
            {(healthError || displayWarning) && (
              <div className="setup-warning">
                <CircleAlert size={19} />
                <div>
                  <strong>
                    {healthError
                      ? "The workspace server is unavailable"
                      : !health?.configured
                        ? "Connect your model provider"
                        : "Add your knowledge sources"}
                  </strong>
                  <p>
                    {healthError ||
                      (!health?.configured
                        ? "Set OPENROUTER_API_KEY in the backend .env file and restart the server. Your key stays on the server."
                        : "Run the ingestion command from the README to index your corpus, then refresh the workspace.")}
                  </p>
                </div>
                <button
                  className="button button-outline button-small"
                  onClick={() => void loadStatus()}
                >
                  <RefreshCw size={14} />
                  Refresh
                </button>
              </div>
            )}
            <div className="ask-layout">
              <div className="ask-column">
                <form
                  className={`question-card ${loading ? "is-loading" : ""}`}
                  onSubmit={ask}
                >
                  <label className="question-label" htmlFor="question">
                    <Search size={18} />
                    <span>What would you like to know?</span>
                  </label>
                  <textarea
                    ref={inputRef}
                    id="question"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="Ask about a decision, a project, or what comes next…"
                    maxLength={4000}
                    rows={3}
                    disabled={loading}
                    onKeyDown={(e) => {
                      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                        e.preventDefault();
                        e.currentTarget.form?.requestSubmit();
                      }
                    }}
                  />
                  <div className="question-footer">
                    <span>
                      <ShieldCheck size={14} /> Grounded in your sources
                    </span>
                    <button
                      className="button button-primary"
                      disabled={
                        !question.trim() ||
                        loading ||
                        !!displayWarning ||
                        !!healthError ||
                        !health
                      }
                    >
                      {loading ? (
                        <LoaderCircle size={16} className="spin" />
                      ) : null}
                      {loading ? "Finding evidence…" : "Ask workspace"}
                      {!loading && <ArrowRight size={16} />}
                    </button>
                  </div>
                </form>
                {queryError && (
                  <ErrorNotice onClose={() => setQueryError("")}>
                    {queryError}
                  </ErrorNotice>
                )}
                {loading && (
                  <div className="search-progress" role="status">
                    <div className="search-orb">
                      <Sparkles size={20} />
                    </div>
                    <div>
                      <strong>Connecting the dots</strong>
                      <p>
                        Finding relevant passages and checking the evidence
                        behind each claim.
                      </p>
                    </div>
                    <div className="loading-dots">
                      <span />
                      <span />
                      <span />
                    </div>
                  </div>
                )}
                {!result && !loading && (
                  <>
                    <div className="section-heading">
                      <h2>A few starting points</h2>
                      <span>Make the question your own</span>
                    </div>
                    <div className="sample-questions">
                      {samples.map((sample) => (
                        <button
                          key={sample.label}
                          onClick={() => {
                            setQuestion(sample.question);
                            inputRef.current?.focus();
                          }}
                        >
                          <span className="sample-icon">
                            <sample.icon size={18} />
                          </span>
                          <div>
                            <span>{sample.label}</span>
                            <p>{sample.question}</p>
                          </div>
                          <ArrowUpRight size={16} />
                        </button>
                      ))}
                    </div>
                    <div className="knowledge-strip">
                      <div className="knowledge-icon">
                        <Layers3 size={21} />
                      </div>
                      <div>
                        <strong>
                          {health
                            ? `${health.document_count} documents`
                            : "Your shared knowledge"}
                        </strong>
                        <span>Meetings, documents, decks & spreadsheets</span>
                      </div>
                      <span className="live-label">
                        <span
                          className={`status-dot ${health?.ready ? "ready" : "warning"}`}
                        />
                        {health?.ready ? "Indexed" : "Awaiting setup"}
                      </span>
                    </div>
                    <div className="trust-caption">
                      <BookOpen size={14} />
                      <span>
                        If the sources don’t know, we’ll say so—and help you
                        find who does.
                      </span>
                    </div>
                  </>
                )}
                {result && (
                  <div ref={resultRef} className="result-area">
                    <section className="answer-card">
                      <div className="answer-heading">
                        <StatusPill status={result.status} />
                        <span>
                          {result.evidence.length} passage
                          {result.evidence.length === 1 ? "" : "s"} retrieved
                        </span>
                      </div>
                      <h2>{result.question}</h2>
                      <AnswerClaims result={result} onEvidence={setSelection} />
                      {result.evidence.length > 0 && (
                        <div className="all-evidence">
                          <span className="eyebrow">Explore the evidence</span>
                          <div>
                            {result.evidence.map((e, i) => (
                              <button
                                key={e.chunk_id}
                                className={`evidence-tab ${selection?.evidence.chunk_id === e.chunk_id ? "active" : ""}`}
                                onClick={() => setSelection({ evidence: e })}
                              >
                                <span>{i + 1}</span>
                                <FileText size={13} />
                                {e.filename}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                      {result.claims.length > 0 && (
                        <Feedback
                          key={result.query_id}
                          result={result}
                          onSaved={() => void loadReviews()}
                        />
                      )}
                    </section>
                    {result.status !== "answered" && (
                      <RoutingDraft
                        key={result.query_id}
                        result={result}
                        onSaved={() => void loadOutbox()}
                        onEvidence={setSelection}
                      />
                    )}
                    <button
                      className="text-button new-question"
                      onClick={() => {
                        setResult(null);
                        setSelection(null);
                        setQuestion("");
                        inputRef.current?.focus();
                      }}
                    >
                      <Plus size={15} />
                      Start a new question
                    </button>
                  </div>
                )}
              </div>
              <EvidencePanel
                selection={selection}
                evidence={result?.evidence || []}
                onSelect={setSelection}
                onClose={() => setSelection(null)}
              />
            </div>
            <footer className="page-footer">
              <span>RELAY AI</span>
              <span>Team knowledge. Clearer decisions.</span>
              <span>AI answers deserve human judgment.</span>
            </footer>
          </div>
        ) : view === "review" ? (
          <ReviewView
            items={reviewItems}
            loading={reviewLoading}
            error={reviewError}
            reload={loadReviews}
            selectedId={selectedReviewId}
            setSelectedId={setSelectedReviewId}
            onEvidence={(e, all) => {
              setReviewEvidence(e);
              setDrawerEvidence(all);
            }}
          />
        ) : (
          <OutboxView
            items={outboxItems}
            error={outboxError}
            loading={outboxLoading}
            reload={loadOutbox}
            openQuery={openQuery}
          />
        )}
      </main>
      {reviewEvidence && (
        <div className="drawer-overlay" onClick={() => setReviewEvidence(null)}>
          <div
            className="drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Review source evidence"
            onClick={(e) => e.stopPropagation()}
          >
            <EvidencePanel
              selection={reviewEvidence}
              evidence={drawerEvidence}
              onSelect={setReviewEvidence}
              onClose={() => setReviewEvidence(null)}
            />
          </div>
        </div>
      )}
      {showStatus && (
        <div className="modal-overlay" onClick={() => setShowStatus(false)}>
          <section
            className="status-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="status-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="detail-heading">
              <span className="eyebrow">Workspace health</span>
              <button
                className="icon-button"
                onClick={() => setShowStatus(false)}
                aria-label="Close status"
              >
                <X size={18} />
              </button>
            </div>
            <h2 id="status-title">{statusText}</h2>
            {healthError && <ErrorNotice>{healthError}</ErrorNotice>}
            {health && (
              <>
                <div className="health-stats">
                  <div>
                    <strong>{health.document_count}</strong>
                    <span>Source documents</span>
                  </div>
                  <div>
                    <strong>{health.chunk_count}</strong>
                    <span>Indexed passages</span>
                  </div>
                </div>
                <dl className="source-metadata">
                  <div>
                    <dt>Model</dt>
                    <dd>{health.model}</dd>
                  </div>
                  <div>
                    <dt>Provider</dt>
                    <dd>
                      {health.configured
                        ? "Configured securely on server"
                        : "OPENROUTER_API_KEY is missing"}
                    </dd>
                  </div>
                  <div>
                    <dt>Evaluation</dt>
                    <dd>
                      {quality?.latest
                        ? "Results available"
                        : "No evaluation has run yet"}
                    </dd>
                  </div>
                </dl>
                {[...health.warnings, ...(quality?.alerts || [])].map(
                  (warning, i) => (
                    <div key={i} className="notice warning">
                      <CircleAlert size={16} />
                      <span>{warning}</span>
                    </div>
                  ),
                )}
                {quality?.latest && (
                  <details className="quality-details">
                    <summary>Latest evaluation details</summary>
                    <pre>{JSON.stringify(quality.latest, null, 2)}</pre>
                  </details>
                )}
              </>
            )}
            <button
              className="button button-outline"
              onClick={() => void loadStatus()}
            >
              <RefreshCw size={15} />
              Check again
            </button>
          </section>
        </div>
      )}
    </div>
  );
}
