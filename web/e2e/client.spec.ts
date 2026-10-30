import { expect, test } from "@playwright/test";
import {
  ROUTES,
  SITE_ID,
  SURVEY_ID,
  collectConsoleErrors,
  collectFailedApiResponses,
  expectNoHorizontalOverflow,
  stubBasemap,
} from "./support";

/**
 * The typed client path in mock mode: MSW answers every §6.3 GET, so no route
 * shows the app's API error text and no `/api/` response fails.
 */
test("no route shows an API error and no /api/ response fails", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const failedApiResponses = collectFailedApiResponses(page);
  await stubBasemap(page);

  for (const route of ROUTES) {
    await page.goto(route.path);

    await expect(page.getByRole("main")).toContainText(route.heading);

    // The health readout is the client's own probe: it must be healthy.
    const health = page.getByRole("banner").getByRole("status");
    await expect(health).toContainText("models ok", { timeout: 10_000 });
    await expect(health).not.toContainText("API unreachable");

    // The error copy ui.md prescribes when the client cannot reach the API.
    await expect(page.getByText("Couldn't reach the ReefCase API")).toHaveCount(0);
    await expect(page.getByText("API unreachable")).toHaveCount(0);

    await expectNoHorizontalOverflow(page, route.path);
  }

  expect(failedApiResponses, "failed /api/ responses").toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test("the mock survey and site resolve by their real ids", async ({ page }) => {
  await stubBasemap(page);

  await page.goto(`/surveys/${SURVEY_ID}`);
  await expect(page.getByRole("main")).toContainText(SURVEY_ID);
  // The mock paces the event stream, so findings arrive a few seconds in.
  await expect(page.getByRole("main")).toContainText("Findings", { timeout: 15_000 });

  await page.goto(`/sites/${SITE_ID}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Lizard Island");
  await expect(page.getByRole("main")).toContainText("Cover over time");
});
