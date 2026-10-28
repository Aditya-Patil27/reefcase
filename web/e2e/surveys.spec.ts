import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  SURVEY_ID,
  collectConsoleErrors,
  expectNoHorizontalOverflow,
  stubBasemap,
} from "./support";

test("/surveys/$id renders live investigation view with frames, trace, and findings", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await stubBasemap(page);

  await page.goto(`/surveys/${SURVEY_ID}`);

  // Header readout contains survey ID and Lizard Island
  await expect(page.getByRole("heading", { name: "Lizard Island" })).toBeVisible();
  await expect(page.getByText(SURVEY_ID).first()).toBeVisible();

  // Pipeline stages (responsive)
  const isMobile = (page.viewportSize()?.width ?? 1440) < 640;
  if (isMobile) {
    await expect(page.getByText(/Stage \d\/6/)).toBeVisible();
  } else {
    await expect(page.getByText("Upload").first()).toBeVisible();
    await expect(page.getByText("Frames").first()).toBeVisible();
    await expect(page.getByText("Segment").first()).toBeVisible();
    await expect(page.getByText("Investigate").first()).toBeVisible();
  }

  // Switch to Frames tab if case file report is active
  const framesTab = page.getByRole("button", { name: "Frames", exact: true });
  if (await framesTab.isVisible()) {
    await framesTab.click();
  }

  // FRAMES section
  await expect(page.getByRole("heading", { name: "FRAMES" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Frame", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Mask", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Both", exact: true })).toBeVisible();

  // Frame tiles and thumbnails appear from mock event stream
  await expect(page.getByText("Frame 01").first()).toBeVisible();

  // TRACE section
  await expect(page.getByRole("heading", { name: "TRACE" }).first()).toBeVisible();
  await expect(page.getByText("Heat stress").first()).toBeVisible();
  await expect(page.getByText("Vessel activity").first()).toBeVisible();

  // FINDINGS section
  await expect(page.getByRole("heading", { name: "FINDINGS" }).first()).toBeVisible();

  // Save screenshot of live investigation at this viewport size
  const viewport = page.viewportSize();
  const width = viewport ? viewport.width : 1440;
  const rootDir = process.cwd().endsWith("web") ? path.resolve("..") : process.cwd();
  const outDir = path.join(rootDir, ".scratch/ui/6-3-live-investigation-view");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }
  await page.screenshot({ path: path.join(outDir, `surveys-${width}.png`) });

  // No horizontal overflow check
  await expectNoHorizontalOverflow(page, `/surveys/${SURVEY_ID}`);
  expect(consoleErrors).toEqual([]);
});
