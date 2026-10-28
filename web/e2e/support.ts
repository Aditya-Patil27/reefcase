import { expect, type Page } from "@playwright/test";
import basemapStyle from "./fixtures/basemap-style.json" with { type: "json" };

/** The mock survey and site ids in web/src/mocks/handlers.ts and events.json. */
export const SURVEY_ID = "srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3";
export const SITE_ID = "site_lizard_island";

export type RouteCase = {
  /** Path to open. */
  path: string;
  /** Section label the placeholder route renders. */
  heading: string;
  /** Slug used in screenshot file names. */
  slug: string;
};

/** Every route Story 6.1 renders inside AppShell (docs/agents/ui.md). */
export const ROUTES: readonly RouteCase[] = [
  { path: "/", heading: "SITES", slug: "root" },
  { path: "/upload", heading: "CLIP", slug: "upload" },
  { path: `/surveys/${SURVEY_ID}`, heading: "FINDINGS", slug: "surveys" },
  { path: `/sites/${SITE_ID}`, heading: "COVER OVER TIME", slug: "sites" },
];

/**
 * Keep the browser offline: the basemap style is served from a fixture, and the
 * fixture itself declares no tile or glyph sources. Story 6.4 adds MapLibre;
 * stubbing now means the spec never needs the network.
 */
export async function stubBasemap(page: Page): Promise<void> {
  await page.route("https://basemaps.cartocdn.com/**", (route) =>
    route.fulfill({ json: basemapStyle }),
  );
}

/** Collect console errors and uncaught exceptions for the life of the page. */
export function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

/** Collect every `/api/` response that failed, so a missing mock handler is visible. */
export function collectFailedApiResponses(page: Page): string[] {
  const failed: string[] = [];
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (!url.pathname.startsWith("/api/") || response.status() < 400) return;
    failed.push(`${response.status()} ${response.request().method()} ${url.pathname}`);
  });
  return failed;
}

/** Assert `document.documentElement.scrollWidth <= window.innerWidth`, with numbers on failure. */
export async function expectNoHorizontalOverflow(page: Page, label: string): Promise<void> {
  const { scrollWidth, innerWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  expect(
    scrollWidth,
    `${label} overflows horizontally: document is ${scrollWidth}px in a ${innerWidth}px viewport`,
  ).toBeLessThanOrEqual(innerWidth);
}
