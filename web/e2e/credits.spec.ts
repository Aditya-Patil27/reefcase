import { expect, test } from "@playwright/test";
import { collectConsoleErrors, expectNoHorizontalOverflow, stubBasemap } from "./support";

/**
 * Architecture §9.9 plus the basemap. Each row is asserted by source, licence and
 * the obligation string the licence requires.
 */
const ATTRIBUTIONS = [
  ["Global Fishing Watch", "CC BY-NC 4.0", "Powered by Global Fishing Watch"],
  ["NOAA Coral Reef Watch", "US Government work", "PIFSC ESD"],
  ["Allen Coral Atlas", "CC BY 4.0", "doi:10.5281/zenodo.3833242"],
  ["WDPA", "Non-commercial", "UNEP-WCMC"],
  ["Coralscapes", "Apache-2.0", "Coralscapes paper"],
  ["Ifremer", "CC BY 4.0", "Credit Ifremer"],
  ["SAM 3", "SAM License", "Acknowledge SAM"],
  ["Muse Spark Open", "Muse Model License", "Built with Muse Spark Open"],
  ["CARTO", "OpenStreetMap", "OpenStreetMap contributors"],
] as const;

test("Data credits opens exactly one panel listing every attribution", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await stubBasemap(page);
  await page.goto("/");

  const trigger = page.getByRole("button", { name: "Data credits" });
  await expect(trigger).toHaveAttribute("aria-expanded", "false");

  await trigger.click();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");

  // One panel, not one badge per layer.
  const panels = page.getByRole("dialog");
  await expect(panels).toHaveCount(1);
  const panel = page.getByRole("dialog", { name: "Data credits" });
  await expect(panel).toBeVisible();

  for (const [source, licence, obligation] of ATTRIBUTIONS) {
    await expect(panel, `${source} attribution`).toContainText(source);
    await expect(panel, `${source} licence`).toContainText(licence);
    await expect(panel, `${source} obligation`).toContainText(obligation);
  }

  await expect(panel.getByText("Powered by Global Fishing Watch")).toHaveCount(1);
  await expect(panel).toContainText("IUCN");

  // The panel must sit inside the viewport and must not widen the document
  // (it matters most at 390x844).
  const viewport = page.viewportSize();
  const box = await panel.boundingBox();
  expect(viewport).not.toBeNull();
  expect(box).not.toBeNull();
  if (viewport && box) {
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
    expect(box.y).toBeGreaterThanOrEqual(0);
    expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
  }
  await expectNoHorizontalOverflow(page, "Data credits open");

  // Toggling closed leaves no panel behind.
  await trigger.click();
  await expect(panels).toHaveCount(0);

  expect(consoleErrors).toEqual([]);
});
