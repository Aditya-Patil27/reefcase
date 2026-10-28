import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  SURVEY_ID,
  collectConsoleErrors,
  expectNoHorizontalOverflow,
  stubBasemap,
} from "./support";

test("/surveys/$id displays CaseFile on report ready and opens EvidenceDrawer", async ({
  page,
}) => {
  const consoleErrors = collectConsoleErrors(page);
  await stubBasemap(page);

  await page.goto(`/surveys/${SURVEY_ID}`);

  // Once investigation report is ready, CaseFile renders with verdict and sections
  await expect(
    page.getByText(/Thermal stress drove most of the bleaching/i),
  ).toBeVisible({ timeout: 15_000 });

  // FINDINGS
  await expect(page.getByRole("heading", { name: "FINDINGS" }).first()).toBeVisible();

  // HYPOTHESES with confidence percentage
  await expect(page.getByRole("heading", { name: "HYPOTHESES" })).toBeVisible();
  await expect(page.getByText("62%")).toBeVisible();

  // ACTIONS
  await expect(page.getByRole("heading", { name: "ACTIONS" })).toBeVisible();
  await expect(
    page.getByText(/Re-survey the same transect in February 2027/i),
  ).toBeVisible();

  // Click an evidence chip to open EvidenceDrawer
  const evidenceChip = page.getByRole("button", { name: /Open evidence: Frame/ }).first();
  await expect(evidenceChip).toBeVisible();
  await evidenceChip.click();

  // Evidence drawer opens
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(page.getByRole("button", { name: "Both", exact: true })).toBeVisible();

  // Save screenshots of CaseFile + open EvidenceDrawer
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
  expect(consoleErrors).toEqual([]);
});
