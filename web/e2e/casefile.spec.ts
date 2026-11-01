import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  SITE_ID,
  SURVEY_ID,
  collectConsoleErrors,
  expectNoHorizontalOverflow,
  stubBasemap,
} from "./support";

test("/surveys/$id displays CaseFile on report ready and opens Evidence on stage", async ({
  page,
}) => {
  const consoleErrors = collectConsoleErrors(page);
  await stubBasemap(page);

  await page.goto(`/surveys/${SURVEY_ID}`);

  // Once investigation report is ready, CaseFile renders with verdict and sections
  await expect(
    page.getByText(/Thermal stress drove most of the bleaching/i),
  ).toBeVisible({ timeout: 15_000 });

  // Findings
  await expect(page.getByRole("heading", { name: "Findings" }).first()).toBeVisible();

  // Hypotheses with confidence percentage
  await expect(page.getByRole("heading", { name: "Hypotheses" })).toBeVisible();
  await expect(page.getByText("62%")).toBeVisible();

  // Actions
  await expect(page.getByRole("heading", { name: "Actions" })).toBeVisible();
  await expect(
    page.getByText(/Re-survey the same transect in February 2027/i),
  ).toBeVisible();

  // Click an evidence chip to put frame on stage
  const evidenceChip = page.getByRole("button", { name: /Open evidence: Frame/ }).first();
  await expect(evidenceChip).toBeVisible();
  await evidenceChip.click();

  // Stage shows that frame (the Both control and the catalogue number)
  await expect(page.getByRole("button", { name: "Both", exact: true })).toBeVisible();
  await expect(page.getByText(/^RC-/).first()).toBeVisible();

  // Click a tool key and see its source on the stage
  const toolChip = page.getByRole("button", { name: /Open evidence:/ }).filter({ hasText: /^T\d+/ }).first();
  await expect(toolChip).toBeVisible();
  await toolChip.click();
  await expect(page.getByText("Source")).toBeVisible();
  await expect(page.getByRole("link", { name: /https?:\/\// }).first()).toBeVisible();

  // Save screenshots of CaseFile + stage
  const viewport = page.viewportSize();
  const width = viewport ? viewport.width : 1440;
  const rootDir = process.cwd().endsWith("web") ? path.resolve("..") : process.cwd();
  const outDir = path.join(rootDir, ".scratch/ui/6-5-case-file-with-evidence-drawer");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }
  await page.screenshot({ path: path.join(outDir, `casefile-${width}.png`) });

  // No horizontal overflow check
  await expectNoHorizontalOverflow(page, `/surveys/${SURVEY_ID}`);

  // Drawer host check on /sites/$id: opening a frame opens the EvidenceDrawer
  await page.goto(`/sites/${SITE_ID}`);
  const siteFrameBtn = page.getByRole("button", { name: /Open Frame 01/i }).first();
  await siteFrameBtn.click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer.getByRole("button", { name: "Both", exact: true })).toBeVisible();

  expect(consoleErrors).toEqual([]);
});
