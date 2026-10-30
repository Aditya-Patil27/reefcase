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

  // Sites section and site rows
  await expect(page.getByRole("heading", { name: "Sites" })).toBeVisible();
  await expect(page.getByText("Lizard Island").first()).toBeVisible();
  await expect(page.getByText("Heron Island").first()).toBeVisible();

  // Layers section and switch toggles
  await expect(page.getByRole("heading", { name: "Layers" })).toBeVisible();
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
  await expect(popover.getByText("37%", { exact: true })).toBeVisible();
  await expect(popover.getByText("2026-10-21")).toBeVisible();
  const openSite = popover.getByRole("link", { name: "Open site" });
  await expect(openSite).toBeVisible();

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

  // The popover leads to the site's page
  await openSite.click();
  await expect(page).toHaveURL(/\/sites\/site_lizard_island$/);
  expect(consoleErrors).toEqual([]);
});
