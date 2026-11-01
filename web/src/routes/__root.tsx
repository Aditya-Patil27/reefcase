import { createRootRoute, Outlet } from "@tanstack/react-router";
import { AppShell } from "../components/AppShell";
import { CrumbProvider } from "../components/crumb";

export const Route = createRootRoute({
  component: RootLayout,
});

function RootLayout() {
  return (
    <CrumbProvider>
      <AppShell>
        <Outlet />
      </AppShell>
    </CrumbProvider>
  );
}
