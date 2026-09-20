import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import type { QueryResult, SourceDocument } from "../src/api";

const source: SourceDocument = {
  document_id: "doc-1",
  filename: "atlas_decision.md",
  title: "Atlas release decision",
  author: "Maya Chen",
  attendees: ["Maya Chen", "Theo Haddad"],
  date: "2026-09-10",
  domain: "Delivery",
  priority: "High",
  decisions: ["Launch depends on the approved security gate."],
  action_items: ["Theo will record the security sign-off."],
  warnings: [],
  chunk_count: 1,
  active: true,
  sha256: "abc123",
  origin: "corpus",
  version_count: 2,
  chunks: [
    {
      chunk_id: "chunk-1",
      document_id: "doc-1",
      filename: "atlas_decision.md",
      title: "Atlas release decision",
      author: "Maya Chen",
      attendees: ["Maya Chen", "Theo Haddad"],
      date: "2026-09-10",
      domain: "Delivery",
      priority: "High",
      locator: "Lines 10-12",
      text: "Launch depends on the approved security gate. Theo will record the security sign-off.",
    },
  ],
  versions: [
    {
      document_id: "doc-1",
      filename: "atlas_decision.md",
      active: true,
      created_at: "2026-09-20T12:00:00Z",
      sha256: "abc123",
    },
    {
      document_id: "doc-old",
      filename: "atlas_decision.md",
      active: false,
      created_at: "2026-09-18T12:00:00Z",
      sha256: "old456",
    },
  ],
};
const answer: QueryResult = {
  query_id: "query-1",
  question: "What is the launch condition?",
  status: "answered",
  claims: [
    {
      text: source.decisions[0],
      citations: [{ chunk_id: "chunk-1", quote: source.decisions[0] }],
    },
  ],
  evidence: source.chunks,
  routing: [],
  message: "",
  created_at: "2026-09-20T12:00:00Z",
};

async function workspace(page: Page, configured = true) {
  const state = {
    documents: [source],
    uploads: [] as { filename: string; body: string }[],
    searches: [] as { question: string }[],
    queries: [] as { question: string }[],
  };
  await page.context().route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.slice(4);
    if (path === "/health")
      return route.fulfill({
        json: {
          configured,
          ready: configured,
          document_count: state.documents.length,
          chunk_count: state.documents.length,
          model: "configured-answer-model",
          warnings: [],
        },
      });
    if (path === "/quality")
      return route.fulfill({
        json: {
          latest: { case_count: 15, passed: 12 },
          alerts: ["Three answer cases have unresolved support findings."],
          open_finding_count: 3,
        },
      });
    if (["/review", "/outbox"].includes(path))
      return route.fulfill({ json: { items: [] } });
    if (path === "/sources")
      return route.fulfill({ json: { items: state.documents } });
    if (path === "/sources/doc-1") return route.fulfill({ json: source });
    if (path === "/upload-samples")
      return route.fulfill({
        json: {
          items: ["kickoff", "escalation"].map((id) => ({
            id,
            title: `Juniper Harbor ${id}`,
            filename: `juniper_${id}.md`,
            description: "A fictional transcript available to add.",
            before_question: `Who owns Juniper ${id}?`,
            after_question: `Who owns Juniper ${id}?`,
            download_url: `/api/upload-samples/${id}/file`,
          })),
        },
      });
    if (path.startsWith("/upload-samples/") && path.endsWith("/file"))
      return route.fulfill({
        contentType: "text/markdown",
        headers: {
          "Content-Disposition": 'attachment; filename="juniper_kickoff.md"',
        },
        body: "# Juniper kickoff\nAuthor: Erin Cole\nDecision: Erin owns the launch review.",
      });
    if (path === "/documents/upload") {
      const filename = url.searchParams.get("filename")!;
      state.uploads.push({
        filename,
        body: request.postDataBuffer()?.toString("utf8") || "",
      });
      const existing = state.documents.some(
        (document) => document.filename === filename,
      );
      if (!existing)
        state.documents.push({
          ...source,
          document_id: `uploaded-${filename}`,
          filename,
          origin: "uploaded",
        });
      return route.fulfill({
        status: existing ? 200 : 201,
        json: {
          filename,
          status: existing ? "unchanged" : "ingested",
          document_id: `uploaded-${filename}`,
          warnings: [],
        },
      });
    }
    if (path === "/search") {
      state.searches.push(request.postDataJSON());
      return route.fulfill({
        json: {
          question: request.postDataJSON().question,
          count: 1,
          evidence: source.chunks,
          message: "Candidate passages only.",
        },
      });
    }
    if (path === "/query") {
      state.queries.push(request.postDataJSON());
      return route.fulfill({
        json: { ...answer, question: request.postDataJSON().question },
      });
    }
    return route.fulfill({
      status: 404,
      json: { detail: `Unexpected test request ${path}` },
    });
  });
  await page.goto("/");
  await expect(
    page.getByRole("button", {
      name: configured ? "Ready" : "Setup needed",
      exact: true,
    }),
  ).toBeVisible();
  return state;
}

test("Documents exposes metadata, extracted text, and preserved version downloads", async ({
  page,
}) => {
  await workspace(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Documents" })
    .click();
  await page.getByLabel("Find a document").fill("Maya");
  const row = page.getByRole("button", {
    name: /atlas_decision.md By Maya Chen/,
  });
  await expect(row).toContainText("Delivery");
  await row.click();
  const dialog = page.getByRole("dialog", { name: "Document details" });
  await expect(dialog).toContainText(source.decisions[0]);
  await expect(dialog).toContainText(source.action_items[0]);
  await dialog.getByText("Full extracted document", { exact: true }).click();
  await expect(
    dialog.getByText(source.chunks[0].text, { exact: true }),
  ).toBeVisible();
  await dialog.getByText("Version history (2)", { exact: true }).click();
  await expect(
    dialog.getByText("Historical version", { exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("link", { name: "Download this version" }).last(),
  ).toHaveAttribute("href", "/api/sources/doc-old/file");
  await page.screenshot({
    path: "../tmp/ui/document-details.png",
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await expect(row).toBeFocused();
  await page.getByLabel("Find a document").fill("no-such-document");
  await expect(page.getByText("No documents match this filter.")).toBeVisible();
});

test("downloaded sample can be uploaded and re-upload reports unchanged", async ({
  page,
}) => {
  const state = await workspace(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Documents" })
    .click();
  await expect(
    page.getByText("Juniper Harbor kickoff", { exact: true }),
  ).toBeVisible();
  expect(state.documents).toHaveLength(1);
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download juniper_kickoff.md" }).click();
  const download = await downloadPromise;
  const file = await download.path();
  // Read downloaded content through the browser's upload control, preserving its filename.
  const fs = await import("node:fs/promises");
  const buffer = await fs.readFile(file!);
  await page.getByLabel("Choose documents").setInputFiles({
    name: download.suggestedFilename(),
    mimeType: "text/markdown",
    buffer,
  });
  await expect(
    page.getByLabel("Upload outcomes").getByText("Indexed", { exact: true }),
  ).toBeVisible();
  expect(state.uploads).toHaveLength(1);
  expect(state.uploads[0]).toMatchObject({
    filename: "juniper_kickoff.md",
    body: expect.stringContaining("Erin owns the launch review"),
  });
  await expect(
    page.getByRole("button", { name: /juniper_kickoff.md By Maya Chen/ }),
  ).toBeVisible();
  await page.getByLabel("Choose documents").setInputFiles({
    name: download.suggestedFilename(),
    mimeType: "text/markdown",
    buffer,
  });
  await expect(
    page.getByLabel("Upload outcomes").getByText("Unchanged", { exact: true }),
  ).toBeVisible();
  expect(state.documents).toHaveLength(2);
  await page.screenshot({ path: "../tmp/ui/documents.png", fullPage: true });
});

test("drag-and-drop surfaces one failed file while another finishes, without invented progress", async ({
  page,
}) => {
  const state = await workspace(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Documents" })
    .click();
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/documents/upload?*", async (route) => {
    await waiting;
    return route.fallback();
  });
  const files = await page.evaluateHandle(() => {
    const transfer = new DataTransfer();
    transfer.items.add(
      new File(["bad"], "unsupported.pdf", { type: "application/pdf" }),
    );
    transfer.items.add(
      new File(["# New meeting\nAuthor: Erin Cole"], "new_meeting.md", {
        type: "text/markdown",
      }),
    );
    return transfer;
  });
  await page
    .locator(".upload-zone")
    .dispatchEvent("drop", { dataTransfer: files });
  await expect(page.getByRole("alert")).toContainText("Unsupported format");
  await expect(
    page.getByText("Uploading and processing", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Processing files…" }),
  ).toBeDisabled();
  release();
  await expect(
    page.getByLabel("Upload outcomes").getByText("Indexed", { exact: true }),
  ).toBeVisible();
  expect(state.uploads).toHaveLength(1);
  expect(state.uploads[0].filename).toBe("new_meeting.md");
});

test("an upload error is visible and a later successful retry can refresh the library", async ({
  page,
}) => {
  await workspace(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Documents" })
    .click();
  let fail = true;
  await page.route("**/api/documents/upload?*", (route) =>
    fail
      ? route.fulfill({
          status: 502,
          json: {
            filename: "new.md",
            status: "failed",
            error: "Provider unavailable.",
            detail: "Provider unavailable.",
          },
        })
      : route.fallback(),
  );
  const file = {
    name: "new.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# New transcript"),
  };
  await page.getByLabel("Choose documents").setInputFiles(file);
  await expect(page.getByRole("alert")).toContainText("Provider unavailable");
  await expect(
    page.getByRole("button", { name: "Choose files" }),
  ).toBeEnabled();
  fail = false;
  await page.getByLabel("Choose documents").setInputFiles(file);
  await expect(
    page.getByLabel("Upload outcomes").getByText("Indexed", { exact: true }),
  ).toBeVisible();
});

test("Developer tools keep search separate from answers and quote command inputs literally", async ({
  page,
  context,
}) => {
  const state = await workspace(page);
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page
    .getByRole("button", { name: "Developer tools", exact: true })
    .click();
  const question = "Where is Maya's $(echo injected) `literal` value?";
  await page.getByLabel("API question").fill(question);
  const quote = (value: string) => `'${value.replaceAll("'", "'\\''")}'`;
  const expected = `curl 'http://127.0.0.1:5173/api/search' -H 'Content-Type: application/json' --data-raw ${quote(JSON.stringify({ question }))}`;
  await expect(page.locator(".command-panel pre")).toHaveText(expected);
  await page.getByRole("button", { name: "Copy command" }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
    expected,
  );
  await page.getByRole("button", { name: "Run request" }).click();
  await expect(page.getByLabel("JSON response")).toContainText('"count": 1');
  expect(state.searches).toEqual([{ question }]);
  expect(state.queries).toHaveLength(0);
  await page.getByLabel("API operation").selectOption("query");
  await expect(
    page.getByRole("button", { name: "Copy command" }),
  ).toBeVisible();
  await page.getByLabel("Command format").selectOption("powershell");
  const powershell = `$body = '${JSON.stringify({ question }).replaceAll("'", "''")}'; Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:5173/api/query' -ContentType 'application/json' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))`;
  await expect(page.locator(".command-panel pre")).toHaveText(powershell);
  await page.getByRole("button", { name: "Run request" }).click();
  expect(state.queries).toEqual([{ question }]);
  await expect(page.getByLabel("JSON response")).toContainText(
    '"query_id": "query-1"',
  );
  await page.screenshot({
    path: "../tmp/ui/developer-tools.png",
    fullPage: true,
  });
});

test("Developer request failure retains input and retry stays in the selected operation", async ({
  page,
}) => {
  const state = await workspace(page);
  await page
    .getByRole("button", { name: "Developer tools", exact: true })
    .click();
  let fail = true;
  await page.route("**/api/search", (route) =>
    fail
      ? route.fulfill({
          status: 503,
          json: { detail: "Embedding service timed out." },
        })
      : route.fallback(),
  );
  await page.getByLabel("API question").fill("Find the release gate.");
  await page.getByRole("button", { name: "Run request" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Embedding service timed out",
  );
  await expect(page.getByLabel("API question")).toHaveValue(
    "Find the release gate.",
  );
  fail = false;
  await page.getByRole("button", { name: "Run request" }).click();
  await expect(page.getByLabel("JSON response")).toContainText("chunk-1");
  expect(state.queries).toHaveLength(0);
});

test("source modal retries unavailable full text without losing its citation", async ({
  page,
}) => {
  await workspace(page);
  let fail = true;
  await page.route("**/api/sources/doc-1", (route) =>
    fail
      ? route.fulfill({
          status: 503,
          json: { detail: "Source archive unavailable." },
        })
      : route.fallback(),
  );
  await page.getByLabel("What would you like to know?").fill(answer.question);
  await page
    .getByRole("button", { name: "Ask workspace", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.locator(".citation-attributed").first().click();
  const dialog = page.getByRole("dialog", { name: "Source evidence" });
  await dialog.getByText("Full extracted document", { exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText(
    "Source archive unavailable",
  );
  await expect(dialog.locator("blockquote")).toContainText(source.decisions[0]);
  fail = false;
  await dialog.getByRole("button", { name: "Retry document" }).click();
  await expect(
    dialog.getByText(source.chunks[0].text, { exact: true }).last(),
  ).toBeVisible();
});

test("About explains the fictional workspace and new screens remain usable at 320px", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await workspace(page);
  await page
    .getByRole("button", { name: "About this workspace", exact: true })
    .first()
    .click();
  for (const client of ["Atlas Forge", "Beacon Route", "Cedar Vale"])
    await expect(page.getByText(client, { exact: true })).toBeVisible();
  await expect(
    page.getByText(/The initial corpus contains 24 fictional documents/),
  ).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Documents" })
    .click();
  await expect(
    page.getByRole("button", { name: /atlas_decision.md By Maya Chen/ }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../tmp/ui/mobile-documents.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Developer tools", exact: true })
    .click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("readiness and actual evaluation failure count stay distinct", async ({
  page,
}) => {
  await workspace(page);
  await expect(
    page.getByRole("button", { name: "Ready", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Answer evaluations: 3 failed cases" }),
  ).toHaveClass(/quality-warning/);
  await page
    .getByRole("button", { name: "Answer evaluations: 3 failed cases" })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "These check generated answers, not manual approval of each document.",
  );
});

for (const endpoint of ["sources", "upload-samples"] as const) {
  test(`malformed ${endpoint} responses stay recoverable in Documents`, async ({
    page,
  }) => {
    await workspace(page);
    let fail = true;
    await page.route(`**/api/${endpoint}`, (route) =>
      fail ? route.fulfill({ json: { items: [null] } }) : route.fallback(),
    );
    await page.reload();
    await page
      .getByRole("navigation")
      .getByRole("button", { name: "Documents" })
      .click();
    await expect(page.getByRole("alert")).toContainText("invalid response");
    fail = false;
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: /atlas_decision.md By Maya Chen/ }),
    ).toBeVisible();
  });
}

test("malformed source details do not hide the citation or crash the modal", async ({
  page,
}) => {
  await workspace(page);
  await page.route("**/api/sources/doc-1", (route) =>
    route.fulfill({ json: {} }),
  );
  await page.getByLabel("What would you like to know?").fill(answer.question);
  await page
    .getByRole("button", { name: "Ask workspace", exact: true })
    .click();
  await page.locator(".citation-attributed").first().click();
  await page.getByText("Full extracted document", { exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("invalid response");
  await expect(page.getByRole("dialog").locator("blockquote")).toHaveText(
    source.decisions[0],
  );
});

test("malformed upload and search successes are not represented as successful operations", async ({
  page,
}) => {
  await workspace(page);
  await page.route("**/api/documents/upload?*", (route) =>
    route.fulfill({
      json: {
        filename: "new.md",
        status: "ingested",
        document_id: "new",
        warnings: "broken",
      },
    }),
  );
  await page.route("**/api/search", (route) =>
    route.fulfill({
      json: { question: "test", evidence: "broken", count: 1, message: "" },
    }),
  );
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Documents" })
    .click();
  await page.getByLabel("Choose documents").setInputFiles({
    name: "new.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# New"),
  });
  await expect(page.getByRole("alert")).toContainText("invalid response");
  await expect(
    page.getByLabel("Upload outcomes").getByText("Failed", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Developer tools", exact: true })
    .click();
  await page.getByRole("button", { name: "Run request" }).click();
  await expect(page.getByRole("alert")).toContainText("invalid response");
  await expect(page.getByLabel("JSON response")).toHaveCount(0);
});

test("pending upload state survives navigation and refuses a second local upload", async ({
  page,
}) => {
  const state = await workspace(page);
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/documents/upload?*", async (route) => {
    await waiting;
    return route.fallback();
  });
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Documents" })
    .click();
  await page.getByLabel("Choose documents").setInputFiles({
    name: "pending.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Pending"),
  });
  await expect(
    page.getByText("Uploading and processing", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Ask", exact: true })
    .click();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Documents" })
    .click();
  await expect(
    page.getByText("Uploading and processing", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Processing files…" }),
  ).toBeDisabled();
  release();
  await expect(
    page.getByLabel("Upload outcomes").getByText("Indexed", { exact: true }),
  ).toBeVisible();
  expect(state.uploads).toHaveLength(1);
});

test("an upload replacement refreshes a currently open library document", async ({
  page,
}) => {
  const state = await workspace(page);
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/documents/upload?*", async (route) => {
    await waiting;
    state.documents = [
      {
        ...source,
        document_id: "replacement",
        author: "Theo Haddad",
        decisions: ["Updated source decision."],
      },
    ];
    return route.fulfill({
      json: {
        filename: source.filename,
        status: "ingested",
        document_id: "replacement",
        warnings: [],
      },
    });
  });
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Documents" })
    .click();
  await page.getByLabel("Choose documents").setInputFiles({
    name: source.filename,
    mimeType: "text/markdown",
    buffer: Buffer.from("# Changed"),
  });
  await page
    .getByRole("button", { name: /atlas_decision.md By Maya Chen/ })
    .click();
  release();
  await expect(page.getByRole("dialog")).toContainText(
    "Updated source decision.",
  );
  await expect(
    page.getByRole("dialog").getByRole("link", { name: "Download original" }),
  ).toHaveAttribute("href", "/api/sources/replacement/file");
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("navigation").getByRole("button", { name: "Documents" }),
  ).toBeFocused();
});

test("unconfigured service permits browsing but disables upload and Developer requests", async ({
  page,
}) => {
  await workspace(page, false);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Documents" })
    .click();
  await expect(
    page.getByRole("button", { name: /atlas_decision.md By Maya Chen/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Choose files" }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Developer tools", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Run request" }),
  ).toBeDisabled();
});

test("refresh preserves the selected uploaded source when a corpus file has the same name", async ({
  page,
}) => {
  const state = await workspace(page);
  const uploaded = {
    ...source,
    document_id: "uploaded-copy",
    origin: "uploaded" as const,
    author: "Theo Haddad",
    decisions: ["Decision from the uploaded source."],
  };
  state.documents.push(uploaded);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Documents" })
    .click();
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  const uploadedRow = page.getByRole("button", {
    name: /atlas_decision.md By Theo Haddad/,
  });
  await expect(uploadedRow).toBeVisible();
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/documents/upload?*", async (route) => {
    await waiting;
    return route.fallback();
  });
  await page
    .getByLabel("Choose documents")
    .setInputFiles({
      name: "unrelated.md",
      mimeType: "text/markdown",
      buffer: Buffer.from("# Another source"),
    });
  await uploadedRow.click();
  release();
  await expect.poll(() => state.documents.length).toBe(3);
  await expect(page.getByRole("dialog")).toContainText(
    "Decision from the uploaded source.",
  );
  await expect(
    page.getByRole("dialog").getByRole("link", { name: "Download original" }),
  ).toHaveAttribute("href", "/api/sources/uploaded-copy/file");
});
