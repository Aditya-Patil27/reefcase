import { expect, test } from "@playwright/test";
import { ROUTES, stubBasemap } from "./support";

test("the active nav link carries the router's active state", async ({ page }) => {
  await stubBasemap(page);
  const nav = page.getByRole("navigation", { name: "Primary" });
  const map = nav.getByRole("link", { name: "Map" });
  const upload = nav.getByRole("link", { name: "Upload" });

  await page.goto("/");
  await expect(map).toHaveAttribute("aria-current", "page");
  await expect(map).toHaveAttribute("data-status", "active");
  await expect(upload).not.toHaveAttribute("aria-current", "page");

  await page.goto("/upload");
  await expect(upload).toHaveAttribute("aria-current", "page");
  await expect(upload).toHaveAttribute("data-status", "active");
  await expect(map).not.toHaveAttribute("aria-current", "page");

  // The survey and site routes are not nav destinations, so neither link claims
  // to be the current page.
  for (const route of ROUTES.slice(2)) {
    await page.goto(route.path);
    await expect(map).not.toHaveAttribute("aria-current", "page");
    await expect(upload).not.toHaveAttribute("aria-current", "page");
  }
});

test("the health dot is decorative and the readout text carries the meaning", async ({ page }) => {
  await stubBasemap(page);
  await page.goto("/");

  const readout = page.getByRole("status");
  await expect(readout).toContainText("models ok");

  // The dot is aria-hidden and empty; the sibling text carries the meaning.
  await expect(readout.locator("[aria-hidden='true']")).toHaveCount(1);
  await expect(readout.locator("span:not([aria-hidden='true'])")).toHaveText("models ok");
});
