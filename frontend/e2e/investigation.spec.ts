import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const ownerToken = "phase7-e2e-owner-token";
const otherToken = "phase7-e2e-other-token";
const python = path.resolve("../.venv/bin/python");
const fixture = path.resolve("../scripts/phase7_e2e_fixture.py");
const portfolioOutput = process.env.INCIDENTGRAPH_PORTFOLIO_OUTPUT;

async function capturePortfolio(page: Page, filename: string) {
  if (!portfolioOutput) return;
  mkdirSync(portfolioOutput, { recursive: true });
  await page.screenshot({
    path: path.join(portfolioOutput, filename),
    fullPage: true,
    animations: "disabled",
    caret: "hide",
  });
}

function fixtureAction(action: "publish" | "resume" | "cleanup", investigationId: string) {
  execFileSync(python, [fixture, action, investigationId], {
    cwd: path.resolve(".."),
    stdio: "pipe",
  });
}

test("real API flow reconnects, drills into evidence, reviews, and preserves refresh state", async ({ page, request }) => {
  let investigationId = "";
  try {
    await page.goto("/");
    await page.getByLabel("Bearer token").fill(ownerToken);
    await page.getByLabel("Keep only for this browser tab").check();
    await page.getByRole("button", { name: "Open console" }).click();
    await expect(page.getByRole("heading", { name: "Start a run" })).toBeVisible();

    await page.getByLabel("Service").selectOption("svc-gateway");
    await page.getByLabel("Incident question").fill(
      "Why did the browser-test gateway latency rise in this bounded window?",
    );
    await page.getByRole("button", { name: "Start investigation" }).click();
    await expect(page.getByRole("heading", { name: /browser-test gateway latency/ })).toBeVisible();
    investigationId = new URL(page.url()).searchParams.get("investigation") ?? "";
    expect(investigationId).not.toBe("");
    await expect(page.getByText("REPLAY").first()).toBeVisible();
    await expect(page.getByText(/Event 1/)).toBeVisible();

    const reconnect = page.waitForRequest((incoming) =>
      incoming.url().endsWith(`/investigations/${investigationId}/events`)
      && incoming.headers()["last-event-id"] === "1",
    );
    await page.getByRole("button", { name: "Reconnect stream" }).click();
    await reconnect;

    fixtureAction("publish", investigationId);
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Investigation report" })).toBeVisible();
    await expect(page.getByText("The browser fixture report is grounded in the API-served latency record.")).toBeVisible();
    await expect(page.getByText("get_metrics")).toBeVisible();
    await expect(page.getByText("ok · 3.7 ms")).toBeVisible();
    await capturePortfolio(page, "01-report-and-review.png");

    await page.getByRole("button", { name: /Open evidence/ }).first().click();
    await expect(page.getByRole("heading", { name: "phase7-e2e-metric" })).toBeVisible();
    await expect(page.getByText("fixture://phase7/playwright/metric")).toBeVisible();
    await expect(page.getByLabel("Metric values over the evidence window")).toBeVisible();
    await capturePortfolio(page, "02-evidence-drilldown.png");
    await page.getByRole("button", { name: "Close evidence" }).click();

    await expect(page.getByText(/Accepting this report authorizes publication only/)).toBeVisible();
    await page.getByLabel("Decision rationale").fill("The cited browser fixture is acceptable.");
    await page.getByRole("button", { name: "Accept report" }).click();
    fixtureAction("resume", investigationId);
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
    await expect(page.getByText("completed").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Ask a follow-up" })).toBeVisible();
    await capturePortfolio(page, "03-completed-and-follow-up.png");

    await page.reload();
    await expect(page.getByRole("heading", { name: /browser-test gateway latency/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Investigation report" })).toBeVisible();
    expect(new URL(page.url()).searchParams.get("investigation")).toBe(investigationId);

    const crossUser = await request.get(
      `http://127.0.0.1:8000/api/v1/investigations/${investigationId}`,
      { headers: { Authorization: `Bearer ${otherToken}` } },
    );
    expect(crossUser.status()).toBe(404);
  } finally {
    if (investigationId) fixtureAction("cleanup", investigationId);
  }
});
