import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  SURVEY_ID,
  collectConsoleErrors,
  expectNoHorizontalOverflow,
  stubBasemap,
} from "./support";

test("/upload renders form, handles clip drop, shows progress and navigates", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await stubBasemap(page);

  await page.goto("/upload");

  // Section headings
  await expect(page.getByRole("heading", { name: "Clip", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Site", exact: true })).toBeVisible();

  // Map group with aria-label="Dive site map"
  await expect(page.getByRole("group", { name: "Dive site map" })).toBeVisible();

  // Coordinates readouts
  await expect(page.locator("#upload-lat-input")).toBeVisible();
  await expect(page.locator("#upload-lon-input")).toBeVisible();
  await expect(page.getByText("14.6680° S")).toBeVisible();
  await expect(page.getByText("145.4610° E")).toBeVisible();

  // Submit button
  const submitButton = page.getByRole("button", { name: "Start investigation" });
  await expect(submitButton).toBeVisible();

  // Save screenshot of initial form at this viewport size in repo root .scratch
  const viewport = page.viewportSize();
  const width = viewport ? viewport.width : 1440;
  const rootDir = process.cwd().endsWith("web") ? path.resolve("..") : process.cwd();
  const outDir = path.join(rootDir, ".scratch/ui/6-2-upload-page");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }
  await page.screenshot({ path: path.join(outDir, `upload-${width}.png`) });

  // Select video file using an in-memory buffer
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: "lizard-island.mp4",
    mimeType: "video/mp4",
    buffer: Buffer.from("synthetic-dive-video-clip-bytes"),
  });

  // Filename appears in the file readout paragraph
  await expect(page.locator("p.truncate", { hasText: "lizard-island.mp4" })).toBeVisible();

  // Submit
  await submitButton.click();

  // Progress bar appears while upload in flight
  await expect(page.getByRole("progressbar")).toBeVisible();

  // Navigates to /surveys/$id
  await expect(page).toHaveURL(new RegExp(`/surveys/${SURVEY_ID}$`), { timeout: 10_000 });
  await expect(page.getByRole("main")).toContainText(SURVEY_ID);

  await expectNoHorizontalOverflow(page, "/upload");
  expect(consoleErrors).toEqual([]);
});
