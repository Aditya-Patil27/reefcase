import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRouter, RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { config } from "./config";
import { routeTree } from "./routeTree.gen";
import "./styles/theme.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

// Each route's code is its own chunk; on a slow link the shell shows this while one loads.
function RoutePending() {
  return (
    <p className="px-4 py-6 text-body text-secondary sm:px-6">
      Loading…
    </p>
  );
}

const router = createRouter({
  routeTree,
  defaultPreload: "intent",
  defaultPendingComponent: RoutePending,
  defaultPendingMs: 300,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

async function startMockWorker() {
  const { worker } = await import("./mocks/browser");
  await worker.start();
}

async function bootstrap() {
  if (config.MOCK_API) await startMockWorker();

  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>,
  );
}

void bootstrap();
