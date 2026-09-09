import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#workspace")).toBeVisible();
});

test("comparison updates, rejects bad pit laps and recovers without stale output", async ({
  page,
}) => {
  const initial = await page.locator("#winner").innerText();
  await page.locator("#pit-loss").fill("40");
  await page.locator("#pit-loss").dispatchEvent("input");
  await expect(page.locator("#winner")).not.toHaveText(initial);
  await page.locator("#pit-1-0").fill("50");
  await expect(page.locator("#simulation-error")).toBeVisible();
  await expect(page.locator("#gap-chart")).toBeHidden();
  await expect(page.locator("#download")).toBeDisabled();
  await page.locator("#reset").click();
  await expect(page.locator("#simulation-error")).toBeHidden();
  await expect(page.locator("#winner")).toHaveText(initial);
  await expect(page.locator("#download")).toBeEnabled();
  await page.locator("#stops-1").selectOption("1");
  await expect(page.locator("#winner")).toHaveText(
    "The strategies finish level.",
  );
});

test("all views are keyboard-operable, responsive and pass WCAG AA automated checks", async ({
  page,
}) => {
  await page.locator("#tab-lab").focus();
  for (const name of ["lab", "explorer", "models", "research"]) {
    await expect(page.locator("#tab-" + name)).toBeFocused();
    await expect(page.locator("#tab-" + name)).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page.locator("#panel-" + name)).toBeVisible();
    const widths = await page.evaluate(() => [
      document.documentElement.scrollWidth,
      innerWidth,
    ]);
    expect(widths[0]).toBeLessThanOrEqual(widths[1]);
    const audit = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(audit.violations).toEqual([]);
    await page.keyboard.press("ArrowRight");
  }
  await expect(page.locator("#tab-lab")).toBeFocused();
});

test("archive exposes real rows and source-quality warnings; metrics match exported data", async ({
  page,
}) => {
  await page.locator("#tab-explorer").click();
  await expect(page.locator("#stint-rows tr")).toHaveCount(20);
  await expect(page.locator("#archive-quality")).toContainText(
    "repeated grid slot(s) 8",
  );
  await page.locator("#explore-event").selectOption("2016:monaco");
  await expect(page.locator("#archive-meta")).toContainText("Monaco");
  await page.locator("#tab-lab").click();
  await expect(page.locator("#event")).toHaveValue("2016:monaco");
  await page.locator("#tab-models").click();
  const data = await (await page.request.get("/data/metrics.json")).json();
  await expect(page.locator("#metric-cards")).toContainText(
    (data.tasks.tyre_strategy.test.accuracy * 100).toFixed(1) + "%",
  );
  await page
    .getByText("Per-race test results and uncertainty", { exact: true })
    .click();
  await expect(page.locator("#per-race-report table")).toHaveCount(3);
  await page
    .getByText("Compare every candidate on the same seasons", { exact: true })
    .click();
  await expect(page.locator("#candidate-results table")).toHaveCount(3);
});

test("research exposes reconciliation, excluded data and measured event stints", async ({
  page,
}) => {
  const data = await (await page.request.get("/data/research.json")).json();
  await page.locator("#tab-research").click();
  await expect(page.locator("#join-evidence")).toContainText(
    "+" + data.quality.joins.recovered_by_aliases,
  );
  await expect(page.locator("#richer-summary")).toContainText(
    "no season column",
  );
  await expect(page.locator("#legacy-experiments tbody tr")).toHaveCount(3);
  await page.locator("#tab-explorer").click();
  await expect(page.locator("#stint-study-table tbody tr")).toHaveCount(
    data.stints.events["2016:bahrain"].length,
  );
  await page.locator("#explore-event").selectOption("2016:monaco");
  await expect(page.locator("#stint-study-table")).toContainText(
    "No stints meet",
  );
});

test("CSV download contains complete per-lap data", async ({ page }) => {
  const downloading = page.waitForEvent("download");
  await page.locator("#download").click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe("pit-window-bahrain-scenario.csv");
  const stream = await download.createReadStream();
  let csv = "";
  for await (const chunk of stream) csv += chunk.toString();
  expect(csv.trim().split("\n")).toHaveLength(58);
  expect(csv).toContain("b_minus_a");
  expect(csv).not.toMatch(/NaN|undefined/);
});

test("bundle failure has an actionable error and does not expose a broken workspace", async ({
  page,
}) => {
  await page.route("**/data/events.json*", (route) =>
    route.fulfill({ status: 503, body: "Unavailable" }),
  );
  await page.reload();
  await expect(page.locator("#load-error")).toBeVisible();
  await expect(page.locator("#workspace")).toBeHidden();
});

test("demo has no third-party runtime requests or console errors", async ({
  page,
}) => {
  const errors = [],
    external = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (!request.url().startsWith("http://127.0.0.1:8765/"))
      external.push(request.url());
  });
  await page.reload();
  await expect(page.locator("#workspace")).toBeVisible();
  await page.locator("#safety-lap").selectOption("17");
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test("release loads without relying on stale unversioned entrypoints or data", async ({
  page,
}) => {
  const staleRequests = [];
  await page.route(/\/(app\.js|style\.css|data\/.*\.json)$/, (route) => {
    staleRequests.push(route.request().url());
    return route.fulfill({ status: 410, body: "Previous release" });
  });
  await page.reload();
  await expect(page.locator("#workspace")).toBeVisible();
  await page.getByRole("tab", { name: "Data & research" }).click();
  await expect(page.locator(".join-counts")).toContainText("+88");
  expect(staleRequests).toEqual([]);
});
