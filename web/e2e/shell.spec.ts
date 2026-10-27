import { expect, test } from "@playwright/test";
import {
  ROUTES,
  collectConsoleErrors,
  expectNoHorizontalOverflow,
  stubBasemap,
} from "./support";

// Runs in both configured projects: desktop-1440 (1440x900) and mobile-390 (390x844).
for (const route of ROUTES) {
  test(`${route.path} renders inside the AppShell from the mock API`, async ({ page }) => {
    const consoleErrors = collectConsoleErrors(page);
    await stubBasemap(page);

    await page.goto(route.path);

    await expect(page.getByRole("banner")).toBeVisible();
    await expect(page.getByRole("link", { name: "ReefCase" })).toBeVisible();

    const primaryNav = page.getByRole("navigation", { name: "Primary" });
    await expect(primaryNav.getByRole("link", { name: "Map" })).toBeVisible();
    await expect(primaryNav.getByRole("link", { name: "Upload" })).toBeVisible();

    // Health readout comes from GET /api/health, served by MSW.
    await expect(page.getByRole("banner").getByRole("status")).toContainText("models ok", { timeout: 10_000 });

    await expect(page.getByRole("contentinfo")).toContainText(
      "Open-weight models · SAM 3 · Muse Spark Open",
    );
    await expect(page.getByRole("button", { name: "Data credits" })).toBeVisible();

    // The route itself rendered, inside the shell.
    await expect(page.getByRole("main")).toContainText(route.heading);

    await expectNoHorizontalOverflow(page, route.path);
    expect(consoleErrors).toEqual([]);
  });
}

test("the shell survives a route change without a reload", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await stubBasemap(page);

  await page.goto("/");
  await expect(page.getByRole("banner").getByRole("status")).toContainText("models ok", { timeout: 10_000 });

  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Upload" }).click();
  await expect(page).toHaveURL(/\/upload$/);
  await expect(page.getByRole("main")).toContainText("CLIP");
  await expect(page.getByRole("contentinfo")).toContainText(
    "Open-weight models · SAM 3 · Muse Spark Open",
  );

  await expectNoHorizontalOverflow(page, "/upload after client-side navigation");
  expect(consoleErrors).toEqual([]);
});
