import "@testing-library/jest-dom/vitest";

class MockIntersectionObserver {
  readonly root: Element | Document | null = null;
  readonly rootMargin: string = "";
  readonly thresholds: ReadonlyArray<number> = [];
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

if (typeof window !== "undefined") {
  window.IntersectionObserver = MockIntersectionObserver as unknown as typeof IntersectionObserver;
}
globalThis.IntersectionObserver = MockIntersectionObserver as unknown as typeof IntersectionObserver;

class MockResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
if (typeof window !== "undefined") {
  window.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;
}
globalThis.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;
