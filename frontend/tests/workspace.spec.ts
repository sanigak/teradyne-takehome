import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import type { OutboxItem, QueryResult, ReviewItem } from "../src/api";

// Provider-independent UI contract tests. The application itself has no mock mode.
const answer: QueryResult = {
  query_id: "query-1",
  question: "When will Atlas Forge launch?",
  status: "answered",
  claims: [
    {
      text: "Atlas Forge now targets November 2 for launch, replacing the October 15 kickoff target.",
      citations: [
        { chunk_id: "chunk-1", quote: "The launch target is now November 2." },
      ],
    },
  ],
  evidence: [
    {
      chunk_id: "chunk-1",
      document_id: "doc-version-1",
      filename: "atlas_launch_review.md",
      title: "Atlas Forge launch review",
      author: "Maya Chen",
      attendees: ["Maya Chen", "Leo Patel"],
      date: "2026-09-10",
      domain: "Deployment",
      priority: "high",
      locator: "Paragraph 4",
      text: "The launch target is now November 2. Maya owns the readiness check.",
    },
  ],
  routing: [],
  message: "The latest decision supersedes the kickoff target.",
  created_at: "2026-09-19T12:00:00Z",
};
const gap: QueryResult = {
  ...answer,
  query_id: "query-2",
  question: "What is the vendor deletion SLA?",
  status: "needs_routing",
  claims: [],
  message: "The signed deletion SLA is not present in the available sources.",
  evidence: [
    {
      ...answer.evidence[0],
      chunk_id: "chunk-2",
      document_id: "doc-version-2",
      filename: "beacon_vendor_notes.docx",
      title: "Beacon Route vendor notes",
      author: "Emma Laurent",
      attendees: ["Emma Laurent"],
      locator: "Paragraph 7",
      text: "Emma Laurent will request the signed deletion SLA from the weather vendor.",
    },
  ],
  routing: [
    {
      recipient: "Emma Laurent",
      reason: "Emma owns vendor follow-up in the contract notes.",
      draft_question:
        "Could you confirm the signed weather vendor deletion SLA for Beacon Route?",
      evidence_ids: ["chunk-2"],
    },
  ],
};

async function mockWorkspace(
  page: Page,
  result: QueryResult = answer,
  configured = true,
) {
  const state = {
    reviews: [] as ReviewItem[],
    outbox: [] as OutboxItem[],
    feedback: [] as { kind: string; comment: string }[],
  };
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api", "");
    const method = request.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    if (path === "/health")
      return json({
        configured,
        ready: configured,
        document_count: 24,
        chunk_count: 72,
        model: "openai/gpt-4.1-mini",
        warnings: configured ? [] : ["OPENROUTER_API_KEY is missing"],
      });
    if (path === "/quality") return json({ latest: null, alerts: [] });
    if (path === "/query" && method === "POST") {
      if (result.status !== "answered")
        state.reviews.push({
          id: "review-gap",
          kind: "gap",
          query_id: result.query_id,
          question: result.question,
          answer: result,
          comment: "",
          status: "open",
          created_at: result.created_at,
          resolution_note: "",
        });
      return json(result);
    }
    if (path.startsWith("/query/")) return json(result);
    if (path === "/review") return json({ items: state.reviews });
    if (path.startsWith("/review/") && method === "PATCH") {
      Object.assign(
        state.reviews.find((item) => item.id === path.split("/").pop())!,
        request.postDataJSON(),
      );
      return json({ ok: true });
    }
    if (path === "/feedback" && method === "POST") {
      const data = request.postDataJSON();
      state.feedback.push(data);
      if (data.kind !== "accepted")
        state.reviews.push({
          id: "review-feedback",
          kind: data.kind,
          query_id: result.query_id,
          question: result.question,
          answer: result,
          comment: data.comment,
          status: "open",
          created_at: result.created_at,
          resolution_note: "",
        });
      return json({ id: "feedback-1" });
    }
    if (path === "/outbox" && method === "POST") {
      const item = {
        ...request.postDataJSON(),
        id: "outbox-1",
        status: "simulated",
        created_at: result.created_at,
      } as OutboxItem;
      state.outbox.push(item);
      return json(item);
    }
    if (path === "/outbox") return json({ items: state.outbox });
    return json({ detail: `Unexpected test request: ${method} ${path}` }, 404);
  });
  await page.goto("/");
  await expect(
    page
      .getByRole("button", {
        name: configured ? "Workspace ready" : "Setup needed",
      })
      .first(),
  ).toBeVisible();
  return state;
}

test("inspect citation, correct an answer, and resolve the preserved review", async ({
  page,
}) => {
  const state = await mockWorkspace(page);
  await page.screenshot({ path: "../tmp/ui/ask.png", fullPage: true });
  await page.getByLabel("What would you like to know?").fill(answer.question);
  await page
    .getByRole("button", { name: "Ask workspace", exact: true })
    .click();
  await expect(page.getByText(answer.claims[0].text)).toBeVisible();
  const citation = page.getByRole("button", {
    name: /1\. atlas_launch_review\.md By Maya Chen/,
  });
  await expect(
    citation.getByText("By Maya Chen", { exact: true }),
  ).toBeVisible();
  await expect(
    citation.getByText("1. atlas_launch_review.md", { exact: true }),
  ).toBeVisible();
  await citation.click();
  const evidence = page.getByRole("complementary", { name: "Source evidence" });
  await expect(evidence.getByText("Maya Chen", { exact: true })).toBeVisible();
  await expect(
    evidence.getByText("Paragraph 4", { exact: true }),
  ).toBeVisible();
  await expect(evidence.getByText("Deployment", { exact: true })).toBeVisible();
  await expect(evidence.getByText("high priority")).toBeVisible();
  await expect(
    evidence.getByRole("link", { name: "Download original" }),
  ).toHaveAttribute("href", "/api/sources/doc-version-1/file");
  await page.screenshot({
    path: "../tmp/ui/answer-evidence.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Correct", exact: true }).click();
  await page
    .getByLabel("What should the answer say?")
    .fill(
      "Confirm whether the November 2 date is conditional on the readiness check.",
    );
  await page.getByRole("button", { name: "Submit correction" }).click();
  await expect(
    page.getByText("Added to the review queue for a team lead."),
  ).toBeVisible();
  expect(state.feedback[0].kind).toBe("corrected");
  await page
    .getByRole("navigation")
    .getByRole("button", { name: /Review queue/ })
    .click();
  await page
    .getByRole("button", { name: /Correction.*When will Atlas Forge launch/ })
    .click();
  await expect(page.getByText("Original answer snapshot")).toBeVisible();
  await expect(page.getByText(answer.claims[0].text)).toBeVisible();
  await expect(
    page.getByRole("button", { name: /atlas_launch_review\.md By Maya Chen/ }),
  ).toBeVisible();
  await page
    .getByLabel("Resolution note")
    .fill(
      "Checked source owner: the readiness check is a launch prerequisite.",
    );
  await page.screenshot({ path: "../tmp/ui/review.png", fullPage: true });
  await page.getByRole("button", { name: "Resolve item" }).click();
  await expect(page.getByRole("button", { name: "Reopen item" })).toBeVisible();
  await page.getByRole("button", { name: /^Resolved/ }).click();
  await expect(
    page.getByRole("button", {
      name: /Correction.*When will Atlas Forge launch/,
    }),
  ).toBeVisible();
  expect(state.reviews[0].status).toBe("resolved");
});

test("edit a source-backed handoff and persist a clearly simulated outbox message", async ({
  page,
}) => {
  const state = await mockWorkspace(page, gap);
  await page.getByLabel("What would you like to know?").fill(gap.question);
  await page
    .getByRole("button", { name: "Ask workspace", exact: true })
    .click();
  await expect(
    page.getByText("More context needed", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Emma owns vendor follow-up in the contract notes."),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "To", exact: true })
    .fill("Emma Laurent · Vendor lead");
  await page
    .getByRole("textbox", { name: "Subject", exact: true })
    .fill("Beacon Route: confirm deletion SLA");
  await page
    .getByRole("textbox", { name: "Message", exact: true })
    .fill("Please share the signed deletion SLA and the agreement location.");
  await page.screenshot({ path: "../tmp/ui/routing.png", fullPage: true });
  await page.getByRole("button", { name: "Simulate send" }).click();
  await expect(
    page.getByText(
      "Draft saved to Outbox as a simulated send. No email was delivered.",
    ),
  ).toBeVisible();
  expect(state.outbox[0].evidence_ids).toEqual(["chunk-2"]);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: /Outbox/ })
    .click();
  await expect(page.getByText("This is a simulated outbox.")).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Beacon Route: confirm deletion SLA",
      level: 2,
    }),
  ).toBeVisible();
  await expect(
    page
      .getByText(
        "Please share the signed deletion SLA and the agreement location.",
        { exact: true },
      )
      .last(),
  ).toBeVisible();
  await page.screenshot({ path: "../tmp/ui/outbox.png", fullPage: true });
  await page.getByRole("button", { name: "View original question" }).click();
  await expect(page.getByRole("heading", { name: gap.question })).toBeVisible();
});

test("provider errors stay actionable and do not create knowledge gaps", async ({
  page,
}) => {
  const state = await mockWorkspace(page);
  await page.route("**/api/query", (route) =>
    route.fulfill({
      status: 502,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "OpenRouter is temporarily unavailable. Try again shortly.",
      }),
    }),
  );
  await page
    .getByLabel("What would you like to know?")
    .fill("When will Atlas Forge launch?");
  await page
    .getByRole("button", { name: "Ask workspace", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "OpenRouter is temporarily unavailable",
  );
  expect(state.reviews).toHaveLength(0);
  await expect(
    page.getByRole("button", { name: "Ask workspace", exact: true }),
  ).toBeEnabled();
});

test("mobile layout keeps question and evidence usable without horizontal overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockWorkspace(page);
  await page.getByLabel("What would you like to know?").fill(answer.question);
  await page
    .getByRole("button", { name: "Ask workspace", exact: true })
    .click();
  await expect(
    page.getByRole("complementary", { name: "Source evidence" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../tmp/ui/mobile-answer.png",
    fullPage: true,
  });
});

test("missing credentials explain backend setup and disable requests", async ({
  page,
}) => {
  await mockWorkspace(page, answer, false);
  await expect(page.getByText("Connect your model provider")).toBeVisible();
  await expect(
    page.getByText(/Set OPENROUTER_API_KEY in the backend/),
  ).toBeVisible();
  await page.getByLabel("What would you like to know?").fill(answer.question);
  await expect(
    page.getByRole("button", { name: "Ask workspace", exact: true }),
  ).toBeDisabled();
});

test("an unrelated question abstains without inventing a contact", async ({
  page,
}) => {
  const unrelated: QueryResult = {
    ...gap,
    question: "Who approved a lunar outpost?",
    evidence: [],
    routing: [],
    message: "No relevant organizational evidence was found.",
  };
  await mockWorkspace(page, unrelated);
  await page
    .getByLabel("What would you like to know?")
    .fill(unrelated.question);
  await page
    .getByRole("button", { name: "Ask workspace", exact: true })
    .click();
  await expect(page.getByText("No supported contact found")).toBeVisible();
  await expect(page.getByRole("button", { name: "Simulate send" })).toHaveCount(
    0,
  );
  await page
    .getByRole("navigation")
    .getByRole("button", { name: /Review queue/ })
    .click();
  await expect(
    page.getByRole("button", {
      name: /Knowledge gap.*Who approved a lunar outpost/,
    }),
  ).toBeVisible();
});

test("claim citations visibly attribute attendees when no author is recorded", async ({
  page,
}) => {
  const attendeeAnswer: QueryResult = {
    ...answer,
    evidence: [{ ...answer.evidence[0], author: null }],
  };
  await mockWorkspace(page, attendeeAnswer);
  await page.getByLabel("What would you like to know?").fill(answer.question);
  await page
    .getByRole("button", { name: "Ask workspace", exact: true })
    .click();
  const citation = page.getByRole("button", {
    name: /atlas_launch_review\.md Attendees: Maya Chen, Leo Patel/,
  });
  await expect(
    citation.getByText("Attendees: Maya Chen, Leo Patel", { exact: true }),
  ).toBeVisible();
});

async function askQuestion(page: Page, question = answer.question) {
  await page.getByLabel("What would you like to know?").fill(question);
  await page.getByRole("button", { name: "Ask workspace", exact: true }).click();
}

test("a late Ask response cannot replace a newer query opened from Outbox", async ({ page }) => {
  const state = await mockWorkspace(page);
  state.outbox.push({ id: "saved", query_id: "stored-query", recipient: "Maya Chen", subject: "Earlier handoff", body: "Check launch readiness.", evidence_ids: ["chunk-1"], status: "simulated", created_at: answer.created_at });
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/query", async (route) => {
    await waiting;
    await route.fulfill({ json: answer });
  });
  const stored = { ...answer, query_id: "stored-query", question: "What was the earlier launch handoff?" };
  await page.route("**/api/query/stored-query", (route) => route.fulfill({ json: stored }));
  await askQuestion(page);
  await expect(page.getByText("Connecting the dots")).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: /Outbox/ }).click();
  await page.getByRole("button", { name: "View original question" }).click();
  await expect(page.getByRole("heading", { name: stored.question })).toBeVisible();
  const completed = page.waitForResponse((response) => response.url().endsWith("/api/query"));
  release();
  await completed;
  await expect(page.getByRole("heading", { name: stored.question })).toBeVisible();
  await expect(page.getByLabel("What would you like to know?")).toHaveValue(stored.question);
});

test("keyboard submit respects unavailable credentials", async ({ page }) => {
  await mockWorkspace(page, answer, false);
  let requests = 0;
  await page.route("**/api/query", (route) => { requests += 1; return route.fulfill({ json: answer }); });
  await page.getByLabel("What would you like to know?").fill(answer.question);
  await page.getByLabel("What would you like to know?").press("Control+Enter");
  await page.getByRole("navigation").getByRole("button", { name: /Review queue/ }).click();
  expect(requests).toBe(0);
});

test("persisted resolution notes survive navigation and page reload", async ({ page }) => {
  const state = await mockWorkspace(page);
  const note = "Confirmed with the source owner; original source is preserved.";
  state.reviews.push({ id: "saved-review", kind: "corrected", query_id: answer.query_id, question: answer.question, answer, comment: "Check the launch condition.", status: "resolved", created_at: answer.created_at, resolution_note: note });
  await page.getByRole("navigation").getByRole("button", { name: /Review queue/ }).click();
  await page.getByRole("button", { name: /^Resolved/ }).click();
  await page.getByRole("button", { name: /Correction.*When will Atlas Forge launch/ }).click();
  await expect(page.getByLabel("Resolution note")).toHaveValue(note);
  await page.getByRole("navigation").getByRole("button", { name: /Outbox/ }).click();
  await page.getByRole("navigation").getByRole("button", { name: /Review queue/ }).click();
  await expect(page.getByLabel("Resolution note")).toHaveValue(note);
  await page.getByRole("button", { name: "Reopen item" }).click();
  await expect.poll(() => state.reviews[0].status).toBe("open");
  expect(state.reviews[0].resolution_note).toBe(note);
  await page.reload();
  await page.getByRole("navigation").getByRole("button", { name: /Review queue/ }).click();
  await page.getByRole("button", { name: /Correction.*When will Atlas Forge launch/ }).click();
  await expect(page.getByLabel("Resolution note")).toHaveValue(note);
});

test("malformed successful API responses display an error and allow retry", async ({ page }) => {
  await mockWorkspace(page);
  let attempts = 0;
  await page.route("**/api/query", (route) => route.fulfill({ json: ++attempts === 1 ? { unexpected: "not a query response" } : answer }));
  await askQuestion(page);
  await expect(page.getByRole("alert")).toContainText(/invalid|unexpected/i);
  await expect(page.getByLabel("What would you like to know?")).toHaveValue(answer.question);
  await page.getByRole("button", { name: "Ask workspace", exact: true }).click();
  await expect(page.getByText(answer.claims[0].text)).toBeVisible();
});

test("failed correction preserves the draft, retries once, and disables duplicate submission", async ({ page }) => {
  const state = await mockWorkspace(page);
  let attempts = 0;
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/feedback", async (route) => {
    attempts += 1;
    if (attempts === 1) return route.fulfill({ status: 503, json: { detail: "Review storage is temporarily unavailable." } });
    await waiting;
    await route.fallback();
  });
  await askQuestion(page);
  await page.getByRole("button", { name: "Correct", exact: true }).click();
  const comment = "The launch needs the security gate; please verify the condition.";
  await page.getByLabel("What should the answer say?").fill(comment);
  await page.getByRole("button", { name: "Submit correction" }).click();
  await expect(page.getByRole("alert")).toContainText("Review storage is temporarily unavailable.");
  await expect(page.getByLabel("What should the answer say?")).toHaveValue(comment);
  await page.getByRole("button", { name: "Submit correction" }).click();
  await expect(page.getByRole("button", { name: "Submit correction" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Yes", exact: true })).toBeDisabled();
  release();
  await expect(page.getByText("Added to the review queue for a team lead.")).toBeVisible();
  expect(state.feedback).toEqual([{ query_id: answer.query_id, kind: "corrected", comment }]);
  expect(state.reviews).toHaveLength(1);
  await page.reload();
  await page.getByRole("navigation").getByRole("button", { name: /Review queue/ }).click();
  await expect(page.getByRole("button", { name: /Correction.*When will Atlas Forge launch/ })).toContainText(comment);
});

test("switching contact and retrying a failed simulated send preserves edits and correct evidence", async ({ page }) => {
  const otherEvidence = { ...gap.evidence[0], chunk_id: "chunk-other", filename: "vendor_followup.md", author: "Priya Raman" };
  const twoContacts = { ...gap, evidence: [...gap.evidence, otherEvidence], routing: [...gap.routing, { recipient: "Priya Raman", reason: "Priya coordinates vendor review.", draft_question: "Please confirm the vendor review.", evidence_ids: ["chunk-other"] }] };
  const state = await mockWorkspace(page, twoContacts);
  let attempts = 0;
  await page.route("**/api/outbox", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    if (++attempts === 1) return route.abort("connectionfailed");
    return route.fallback();
  });
  await askQuestion(page, gap.question);
  await page.getByLabel("Suggested contact").selectOption("1");
  await expect(page.getByRole("textbox", { name: "To", exact: true })).toHaveValue("Priya Raman");
  await expect(page.getByRole("textbox", { name: "Message", exact: true })).toHaveValue("Please confirm the vendor review.");
  await page.getByRole("textbox", { name: "To", exact: true }).fill("Priya Raman / delivery lead");
  await page.getByRole("textbox", { name: "Subject", exact: true }).fill("Edited SLA question");
  await page.getByRole("textbox", { name: "Message", exact: true }).fill("Please send the signed agreement and its location.");
  await page.getByRole("button", { name: "Simulate send" }).click();
  await expect(page.getByRole("alert")).toContainText("Cannot reach the workspace server");
  await expect(page.getByRole("textbox", { name: "To", exact: true })).toHaveValue("Priya Raman / delivery lead");
  await page.getByRole("button", { name: "Simulate send" }).click();
  await expect(page.getByText("Draft saved to Outbox as a simulated send. No email was delivered.")).toBeVisible();
  expect(state.outbox).toHaveLength(1);
  expect(state.outbox[0]).toMatchObject({ recipient: "Priya Raman / delivery lead", subject: "Edited SLA question", evidence_ids: ["chunk-other"] });
  await page.reload();
  await page.getByRole("navigation").getByRole("button", { name: /Outbox/ }).click();
  await expect(page.getByRole("heading", { name: "Edited SLA question", level: 2 })).toBeVisible();
  await expect(page.getByText("Please send the signed agreement and its location.", { exact: true }).last()).toBeVisible();
});

test("review resolve failure preserves its note and safely retries", async ({ page }) => {
  const state = await mockWorkspace(page, gap);
  await askQuestion(page, gap.question);
  await page.getByRole("navigation").getByRole("button", { name: /Review queue/ }).click();
  await page.getByRole("button", { name: /Knowledge gap.*What is the vendor deletion SLA/ }).click();
  let attempts = 0;
  await page.route("**/api/review/review-gap", (route) => ++attempts === 1 ? route.fulfill({ status: 503, json: { detail: "The database is busy. Try again." } }) : route.fallback());
  const note = "Requested the missing signed SLA from the documented owner.";
  await page.getByLabel("Resolution note").fill(note);
  await page.getByRole("button", { name: "Resolve item" }).click();
  await expect(page.getByRole("alert")).toContainText("The database is busy");
  await expect(page.getByLabel("Resolution note")).toHaveValue(note);
  expect(state.reviews[0].status).toBe("open");
  await page.getByRole("button", { name: "Resolve item" }).click();
  await expect(page.getByRole("button", { name: "Reopen item" })).toBeVisible();
  expect(state.reviews[0].resolution_note).toBe(note);
});

test("query failure retries without leaving a stale answer or creating a review gap", async ({ page }) => {
  const state = await mockWorkspace(page);
  await askQuestion(page);
  await expect(page.getByText(answer.claims[0].text)).toBeVisible();
  let attempts = 0;
  await page.route("**/api/query", (route) => ++attempts === 1 ? route.fulfill({ status: 504, json: { detail: "The model timed out. Try again." } }) : route.fallback());
  await askQuestion(page, "Retry the current launch decision.");
  await expect(page.getByRole("alert")).toContainText("The model timed out");
  await expect(page.getByText(answer.claims[0].text)).toHaveCount(0);
  await expect(page.getByLabel("What would you like to know?")).toHaveValue("Retry the current launch decision.");
  expect(state.reviews).toHaveLength(0);
  await page.getByRole("button", { name: "Ask workspace", exact: true }).click();
  await expect(page.getByText(answer.claims[0].text)).toBeVisible();
});

test("malicious question, claim, evidence, and feedback markup render only as text", async ({ page }) => {
  const attack = '<img data-attack="injected" src=x onerror="window.__injected=true">';
  const malicious = { ...answer, question: `Explain ${attack}`, claims: [{ text: `Literal source text: ${attack}`, citations: [{ chunk_id: "chunk-1", quote: attack }] }], evidence: [{ ...answer.evidence[0], text: attack, author: attack, title: `Unsafe markup ${attack}` }] };
  const state = await mockWorkspace(page, malicious);
  await askQuestion(page, malicious.question);
  await expect(page.getByRole("heading", { name: malicious.question })).toBeVisible();
  await expect(page.getByText(malicious.claims[0].text, { exact: true })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Source evidence" }).getByText(attack, { exact: true }).last()).toBeVisible();
  await page.getByRole("button", { name: "Correct", exact: true }).click();
  await page.getByLabel("What should the answer say?").fill(attack);
  await page.getByRole("button", { name: "Submit correction" }).click();
  await expect.poll(() => state.reviews.length).toBe(1);
  await page.getByRole("navigation").getByRole("button", { name: /Review queue/ }).click();
  await page.getByRole("button", { name: /Correction.*Explain/ }).click();
  await expect(page.locator(".review-comment")).toContainText(attack);
  expect(await page.locator("img[data-attack], script[data-attack]").count()).toBe(0);
  expect(await page.evaluate(() => "__injected" in window)).toBe(false);
});

test("status dialog traps keyboard focus and Escape restores its trigger", async ({ page }) => {
  await mockWorkspace(page);
  const trigger = page.getByRole("button", { name: "Workspace ready" }).first();
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Workspace ready" });
  const close = dialog.getByRole("button", { name: "Close status" });
  await expect(close).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.getByRole("button", { name: "Check again" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test("changing source in a review dialog retains focus and Escape returns to its citation", async ({ page }) => {
  const twoSources = { ...answer, evidence: [...answer.evidence, { ...answer.evidence[0], chunk_id: "chunk-2", filename: "atlas_security_gate.md", locator: "Paragraph 9" }] };
  const state = await mockWorkspace(page, twoSources);
  state.reviews.push({ id: "review", kind: "corrected", query_id: answer.query_id, question: answer.question, answer: twoSources, comment: "Check source conditions.", status: "open", created_at: answer.created_at, resolution_note: "" });
  await page.getByRole("navigation").getByRole("button", { name: /Review queue/ }).click();
  await page.getByRole("button", { name: /Correction.*When will Atlas Forge launch/ }).click();
  const trigger = page.getByRole("button", { name: /1\. atlas_launch_review\.md By Maya Chen/ });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Review source evidence" });
  const select = dialog.getByLabel("Retrieved sources");
  await select.focus();
  await select.selectOption("chunk-2");
  await expect(select).toBeFocused();
  await expect(dialog.getByText("Paragraph 9", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test("320px layout tolerates long unbroken source names and questions", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  const longText = "A".repeat(300);
  const narrow = { ...answer, question: `What is ${longText}?`, evidence: [{ ...answer.evidence[0], filename: `${longText}.docx`, author: longText, title: longText }] };
  await mockWorkspace(page, narrow);
  await askQuestion(page, narrow.question);
  await expect(page.getByRole("heading", { name: narrow.question })).toBeVisible();
  const overflowing = await page.evaluate(() => [...document.querySelectorAll("body *")].filter((element) => element.getBoundingClientRect().right > window.innerWidth + 1).map((element) => `${element.tagName}.${element.className}`));
  expect(overflowing).toEqual([]);
  await page.getByRole("button", { name: "Correct", exact: true }).click();
  await page.getByLabel("What should the answer say?").fill(longText);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("navigation during a pending question keeps the selected page and later restores the answer", async ({ page }) => {
  await mockWorkspace(page);
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/query", async (route) => { await waiting; await route.fulfill({ json: answer }); });
  await askQuestion(page);
  await page.getByRole("navigation").getByRole("button", { name: /Review queue/ }).click();
  release();
  await expect(page.getByRole("heading", { name: "Review queue." })).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: /Ask the workspace/ }).click();
  await expect(page.getByText(answer.claims[0].text)).toBeVisible();
  await expect(page.getByLabel("What would you like to know?")).toBeEnabled();
});

for (const endpoint of ["review", "outbox"] as const) {
  test(`malformed ${endpoint} list responses report a recoverable error`, async ({ page }) => {
    await mockWorkspace(page);
    let fail = true;
    await page.route(`**/api/${endpoint}`, (route) => fail ? route.fulfill({ json: { items: [{ broken: true }] } }) : route.fallback());
    await page.getByRole("navigation").getByRole("button", { name: endpoint === "review" ? /Review queue/ : /Outbox/ }).click();
    await expect(page.getByRole("alert")).toContainText("invalid response");
    fail = false;
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
    await expect(page.getByRole("alert")).toHaveCount(0);
  });
}

test("a malformed health response disables asking until a successful refresh", async ({ page }) => {
  await mockWorkspace(page);
  let fail = true;
  await page.route("**/api/health", (route) => fail ? route.fulfill({ json: { ready: true } }) : route.fallback());
  await page.reload();
  await expect(page.getByText("The workspace server is unavailable")).toBeVisible();
  await page.getByLabel("What would you like to know?").fill(answer.question);
  await expect(page.getByRole("button", { name: "Ask workspace", exact: true })).toBeDisabled();
  fail = false;
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByRole("button", { name: "Ask workspace", exact: true })).toBeEnabled();
});

test("failed quality reads are visibly different from an evaluation that has never run", async ({ page }) => {
  await mockWorkspace(page);
  await page.route("**/api/quality", (route) => route.fulfill({ status: 503, json: { detail: "Evaluation storage unavailable." } }));
  await page.reload();
  const badge = page.getByRole("button", { name: "Evaluation unavailable" }).first();
  await expect(badge).toBeVisible();
  await expect(badge.locator(".status-dot")).toHaveClass(/warning/);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByLabel("What would you like to know?").fill(answer.question);
  await expect(page.getByRole("button", { name: "Ask workspace", exact: true })).toBeEnabled();
  await badge.click();
  await expect(page.getByRole("alert")).toContainText("Evaluation status is unavailable");
  await expect(page.getByText("No evaluation has run yet")).toHaveCount(0);
  await expect(page.getByText("Evaluation status unavailable", { exact: true })).toBeVisible();
});

test("quality regressions are visible before opening status and recover after a passing refresh", async ({ page }) => {
  await mockWorkspace(page);
  let failing = true;
  const warning = "Full regression suite needs review: 11 of 12 cases passed.";
  await page.route("**/api/quality", (route) => route.fulfill({ json: { latest: { suite: "full", passed: failing ? 11 : 12, total: 12 }, alerts: failing ? [warning] : [] } }));
  await page.reload();
  const badge = page.getByRole("button", { name: "Quality needs review" }).first();
  await expect(badge).toBeVisible();
  await expect(badge.locator(".status-dot")).toHaveClass(/warning/);
  await expect(page.getByRole("button", { name: "Workspace ready" })).toHaveCount(0);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByLabel("What would you like to know?").fill(answer.question);
  await expect(page.getByRole("button", { name: "Ask workspace", exact: true })).toBeEnabled();
  await badge.click();
  const dialog = page.getByRole("dialog", { name: "Quality needs review" });
  await expect(dialog).toContainText(warning);
  await dialog.getByText("Latest evaluation details").click();
  await expect(dialog.locator("pre")).toContainText('"passed": 11');
  failing = false;
  await dialog.getByRole("button", { name: "Check again" }).click();
  await expect(page.getByRole("dialog", { name: "Workspace ready" })).toBeVisible();
  await page.getByRole("button", { name: "Close status" }).click();
  await expect(page.getByRole("button", { name: "Workspace ready" }).first().locator(".status-dot")).toHaveClass(/ready/);
});

test("missing credentials take priority over a quality warning", async ({ page }) => {
  await mockWorkspace(page, answer, false);
  await page.route("**/api/quality", (route) => route.fulfill({ json: { latest: null, alerts: ["Evaluation needs review."] } }));
  await page.reload();
  await expect(page.getByRole("button", { name: "Setup needed" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Quality needs review" })).toHaveCount(0);
  await page.getByLabel("What would you like to know?").fill(answer.question);
  await expect(page.getByRole("button", { name: "Ask workspace", exact: true })).toBeDisabled();
});

test("an older review refresh cannot hide newer persisted feedback", async ({ page }) => {
  const state = await mockWorkspace(page);
  state.reviews.push({ id: "newest-review", kind: "corrected", query_id: answer.query_id, question: answer.question, answer, comment: "Latest saved correction.", status: "open", created_at: answer.created_at, resolution_note: "" });
  let calls = 0;
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/review", async (route) => {
    if (++calls === 1) { await waiting; return route.fulfill({ json: { items: [] } }); }
    return route.fallback();
  });
  await page.getByRole("navigation").getByRole("button", { name: /Review queue/ }).click();
  await expect.poll(() => calls).toBe(1);
  await page.getByRole("navigation").getByRole("button", { name: /Outbox/ }).click();
  await page.getByRole("navigation").getByRole("button", { name: /Review queue/ }).click();
  const latest = page.getByRole("button", { name: /Correction.*When will Atlas Forge launch/ });
  await expect(latest).toBeVisible();
  const completed = page.waitForResponse((response) => response.url().endsWith("/api/review"));
  release();
  await completed;
  await expect(latest).toBeVisible();
});

test("mobile citation opens evidence into view and closing it restores keyboard focus", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockWorkspace(page);
  await askQuestion(page);
  const citation = page.getByRole("button", { name: /1\. atlas_launch_review\.md By Maya Chen/ });
  await citation.click();
  const evidence = page.getByRole("complementary", { name: "Source evidence" });
  await expect(evidence).toBeFocused();
  await expect(evidence.getByRole("heading", { name: "Source evidence" })).toBeInViewport();
  await evidence.getByRole("button", { name: "Close evidence" }).click();
  await expect(citation).toBeFocused();
});
