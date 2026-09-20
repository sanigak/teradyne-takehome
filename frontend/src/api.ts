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
};

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
  return body as T;
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: "POST", body: JSON.stringify(body) });
}
