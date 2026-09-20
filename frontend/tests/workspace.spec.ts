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
