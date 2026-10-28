import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  collectConsoleErrors,
  expectNoHorizontalOverflow,
  stubBasemap,
} from "./support";

test("/ renders reef map with sites, layers toggles, and site popover", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await stubBasemap(page);

  await page.goto("/");

  // SITES section and site rows
  await expect(page.getByRole("heading", { name: "SITES" })).toBeVisible();
  await expect(page.getByText("Lizard Island").first()).toBeVisible();
  await expect(page.getByText("Heron Island").first()).toBeVisible();

  // LAYERS section and switch toggles
  await expect(page.getByRole("heading", { name: "LAYERS" })).toBeVisible();
  const mpaSwitch = page.getByRole("switch", { name: "MPA boundaries" });
  const reefSwitch = page.getByRole("switch", { name: "Reef extent" });
  const vesselSwitch = page.getByRole("switch", { name: "Vessel activity" });

  await expect(mpaSwitch).toBeVisible();
  await expect(reefSwitch).toBeVisible();
  await expect(vesselSwitch).toBeVisible();

  // Click Lizard Island in left panel to open popover
  const lizardItem = page.getByRole("listitem").filter({ hasText: "Lizard Island" });
  await lizardItem.click();

  // Popover appears with title, coordinates, figure cover, dive date, CoverStrip and links
  const popover = page.getByRole("dialog", { name: "Lizard Island" });
  await expect(popover).toBeVisible();
  await expect(popover.getByText(/14\.6680°\s+S/)).toBeVisible();
  await expect(popover.getByText("37%")).toBeVisible();
  await expect(popover.getByText("2026-10-21")).toBeVisible();
  await expect(popover.getByRole("link", { name: /Site timeline/i })).toBeVisible();
  await expect(popover.getByRole("link", { name: /Latest case file/i })).toBeVisible();

  // Save screenshot of map view at this viewport
  const viewport = page.viewportSize();
  const width = viewport ? viewport.width : 1440;
  const rootDir = process.cwd().endsWith("web") ? path.resolve("..") : process.cwd();
  const outDir = path.join(rootDir, ".scratch/ui/6-4-reef-map");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }
  await page.screenshot({ path: path.join(outDir, `map-${width}.png`) });

  // No horizontal overflow check
  await expectNoHorizontalOverflow(page, "/");
  expect(consoleErrors).toEqual([]);
});
