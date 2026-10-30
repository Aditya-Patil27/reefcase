import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  SITE_ID,
  collectConsoleErrors,
  expectNoHorizontalOverflow,
  stubBasemap,
} from "./support";

test("/sites/$id renders site timeline with metrics, cover chart, and surveys table", async ({
  page,
}) => {
  const consoleErrors = collectConsoleErrors(page);
  await stubBasemap(page);

  await page.goto(`/sites/${SITE_ID}`);

  // Header: site name, coordinates, MPA chip
  await expect(page.getByRole("heading", { name: "Lizard Island" })).toBeVisible();
  await expect(page.getByText(/14.6680°\s+S\s+145.4610°\s+E/i)).toBeVisible();
  await expect(page.getByText("MPA protected")).toBeVisible();

  // One readout line of key figures
  await expect(page.getByLabel("Site key figures")).toHaveText(
    /\d+% live coral [+−]\d+\.\d pp since \d{4} · \d+ surveys/,
  );

  // Cover over time section
  await expect(page.getByRole("heading", { name: "Cover over time" })).toBeVisible();
  await expect(page.getByText("Live coral").first()).toBeVisible();
  await expect(page.getByText("Bleached coral").first()).toBeVisible();

  // Surveys section
  await expect(page.getByRole("heading", { name: "Surveys" })).toBeVisible();

  // Save screenshot of timeline at this viewport size
  const viewport = page.viewportSize();
  const width = viewport ? viewport.width : 1440;
  const rootDir = process.cwd().endsWith("web") ? path.resolve("..") : process.cwd();
  const outDir = path.join(rootDir, ".scratch/ui/6-6-site-timeline");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }
  await page.screenshot({ path: path.join(outDir, `timeline-${width}.png`) });

  // No horizontal overflow check
  await expectNoHorizontalOverflow(page, `/sites/${SITE_ID}`);

  // Click Case file link in table to navigate to survey
  const caseFileLink = page.getByRole("link", { name: /Case file/i }).first();
  await expect(caseFileLink).toBeVisible();
  await caseFileLink.click();
  await expect(page).toHaveURL(new RegExp(`/surveys/`));

  expect(consoleErrors).toEqual([]);
});
