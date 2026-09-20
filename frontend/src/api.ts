export type Evidence = {
  chunk_id: string;
  document_id: string;
  filename: string;
  title: string;
  author: string | null;
  attendees: string[];
  date: string | null;
  domain: string;
  priority: string | null;
  locator: string;
  text: string;
};

export type QueryResult = {
  query_id: string;
  question: string;
  status: "answered" | "partial" | "needs_routing";
  claims: { text: string; citations: { chunk_id: string; quote: string }[] }[];
  evidence: Evidence[];
  routing: {
    recipient: string;
    reason: string;
    draft_question: string;
    evidence_ids: string[];
  }[];
  message: string;
  created_at: string;
};

export type ReviewItem = {
  id: string;
  kind: "gap" | "rejected" | "corrected";
  query_id: string;
  question: string;
  answer: QueryResult;
  comment: string;
  status: "open" | "resolved";
  created_at: string;
  resolution_note: string;
};

export type OutboxItem = {
  id: string;
  query_id: string;
  recipient: string;
  subject: string;
  body: string;
  evidence_ids: string[];
  status: "simulated";
  created_at: string;
};

export type Health = {
  configured: boolean;
  ready: boolean;
  document_count: number;
  chunk_count: number;
  model: string;
  warnings: string[];
};

export type Quality = {
  latest: Record<string, unknown> | null;
  alerts: string[];
  open_finding_count?: number | null;
  suites?: Record<string, unknown>[];
};

export type SourceDocument = {
  document_id: string;
  filename: string;
  title: string;
  author: string | null;
  attendees: string[];
  date: string | null;
  domain: string;
  priority: string | null;
  decisions: string[];
  action_items: string[];
  warnings: string[];
  chunk_count: number;
  active?: boolean;
  sha256?: string;
  origin?: "uploaded" | "corpus";
  version_count?: number;
  chunks: Evidence[];
  versions?: Record<string, unknown>[];
};
export type UploadSample = {
  id: string;
  title: string;
  filename: string;
  description: string;
  before_question: string;
  after_question: string;
  download_url: string;
};

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const strings = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === "string");

function validEvidence(value: unknown): boolean {
  return (
    record(value) &&
    [
      "chunk_id",
      "document_id",
      "filename",
      "title",
      "domain",
      "locator",
      "text",
    ].every((key) => typeof value[key] === "string") &&
    ["author", "date", "priority"].every(
      (key) => value[key] === null || typeof value[key] === "string",
    ) &&
    strings(value.attendees)
  );
}

function validQuery(value: unknown): boolean {
  if (!record(value)) return false;
  return (
    ["query_id", "question", "message", "created_at"].every(
      (key) => typeof value[key] === "string",
    ) &&
    ["answered", "partial", "needs_routing"].includes(String(value.status)) &&
    Array.isArray(value.evidence) &&
    value.evidence.every(validEvidence) &&
    Array.isArray(value.claims) &&
    value.claims.every(
      (claim) =>
        record(claim) &&
        typeof claim.text === "string" &&
        Array.isArray(claim.citations) &&
        claim.citations.every(
          (citation) =>
            record(citation) &&
            typeof citation.chunk_id === "string" &&
            typeof citation.quote === "string",
        ),
    ) &&
    Array.isArray(value.routing) &&
    value.routing.every(
      (route) =>
        record(route) &&
        ["recipient", "reason", "draft_question"].every(
          (key) => typeof route[key] === "string",
        ) &&
        strings(route.evidence_ids),
    )
  );
}

function validSource(value: unknown): value is Record<string, unknown> {
  return (
    record(value) &&
    ["document_id", "filename", "title", "domain"].every(
      (key) => typeof value[key] === "string",
    ) &&
    ["author", "date", "priority"].every(
      (key) => value[key] === null || typeof value[key] === "string",
    ) &&
    ["attendees", "warnings", "decisions", "action_items"].every((key) =>
      strings(value[key]),
    ) &&
    (value.origin === undefined ||
      value.origin === "corpus" ||
      value.origin === "uploaded")
  );
}

function validVersions(value: unknown): boolean {
  return (
    value === undefined ||
    (Array.isArray(value) &&
      value.every(
        (version) =>
          record(version) &&
          typeof version.active === "boolean" &&
          ["document_id", "filename", "created_at", "sha256"].every(
            (key) => typeof version[key] === "string",
          ),
      ))
  );
}

function validReadResponse(
  path: string,
  value: Record<string, unknown>,
): boolean {
  if (path === "/query" || path.startsWith("/query/")) return validQuery(value);
  if (path === "/health")
    return (
      typeof value.configured === "boolean" &&
      typeof value.ready === "boolean" &&
      typeof value.model === "string" &&
      strings(value.warnings) &&
      ["document_count", "chunk_count"].every(
        (key) =>
          typeof value[key] === "number" &&
          Number.isSafeInteger(value[key]) &&
          Number(value[key]) >= 0,
      )
    );
  if (path === "/quality")
    return (
      (value.latest === null || record(value.latest)) &&
      strings(value.alerts) &&
      (value.open_finding_count === undefined ||
        value.open_finding_count === null ||
        (typeof value.open_finding_count === "number" &&
          Number.isSafeInteger(value.open_finding_count) &&
          value.open_finding_count >= 0)) &&
      (value.suites === undefined ||
        (Array.isArray(value.suites) && value.suites.every(record)))
    );
  if (path === "/sources")
    return (
      Array.isArray(value.items) &&
      value.items.every(
        (item) =>
          validSource(item) &&
          typeof item.chunk_count === "number" &&
          Number.isSafeInteger(item.chunk_count) &&
          item.chunk_count >= 0,
      )
    );
  if (path.startsWith("/sources/"))
    return (
      validSource(value) &&
      typeof value.active === "boolean" &&
      Array.isArray(value.chunks) &&
      value.chunks.every(validEvidence) &&
      validVersions(value.versions)
    );
  if (path === "/upload-samples")
    return (
      Array.isArray(value.items) &&
      value.items.every(
        (item) =>
          record(item) &&
          [
            "id",
            "title",
            "filename",
            "description",
            "before_question",
            "after_question",
            "download_url",
          ].every((key) => typeof item[key] === "string") &&
          /^\/api\/upload-samples\/[\w-]+\/file$/.test(
            String(item.download_url),
          ),
      )
    );
  if (path === "/search")
    return (
      typeof value.question === "string" &&
      typeof value.message === "string" &&
      typeof value.count === "number" &&
      Array.isArray(value.evidence) &&
      value.evidence.every(validEvidence) &&
      value.count === value.evidence.length
    );
  if (path.startsWith("/documents/upload?"))
    return (
      typeof value.filename === "string" &&
      ["ingested", "unchanged"].includes(String(value.status)) &&
      typeof value.document_id === "string" &&
      strings(value.warnings)
    );
  if (path === "/review")
    return (
      Array.isArray(value.items) &&
      value.items.every(
        (item) =>
          record(item) &&
          [
            "id",
            "query_id",
            "question",
            "comment",
            "created_at",
            "resolution_note",
          ].every((key) => typeof item[key] === "string") &&
          ["gap", "rejected", "corrected"].includes(String(item.kind)) &&
          ["open", "resolved"].includes(String(item.status)) &&
          validQuery(item.answer),
      )
    );
  if (path === "/outbox")
    return (
      Array.isArray(value.items) &&
      value.items.every(
        (item) =>
          record(item) &&
          [
            "id",
            "query_id",
            "recipient",
            "subject",
            "body",
            "created_at",
          ].every((key) => typeof item[key] === "string") &&
          item.status === "simulated" &&
          strings(item.evidence_ids),
      )
    );
  return true;
}

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options?.headers },
    });
  } catch {
    throw new Error(
      "Cannot reach the workspace server. Start the FastAPI service, then try again.",
    );
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      typeof body?.detail === "string"
        ? body.detail
        : `The request failed (${response.status}). Please try again.`;
    throw new Error(message);
  }
  // A proxy or damaged response must not put invalid data into React state.
  const isRead = !options?.method || options.method.toUpperCase() === "GET";
  if (
    !record(body) ||
    ((isRead ||
      path === "/query" ||
      path === "/search" ||
      path.startsWith("/documents/upload?")) &&
      !validReadResponse(path, body))
  ) {
    throw new Error(
      "The workspace returned an invalid response. Please try again; if this continues, restart the server.",
    );
  }
  return body as T;
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: "POST", body: JSON.stringify(body) });
}
