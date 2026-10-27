import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/sites/$id")({
  component: SiteRoute,
});

/** Placeholder for the site timeline (6.6): a section label and the site readout. */
function SiteRoute() {
  const { id } = Route.useParams();

  return (
    <section aria-labelledby="cover-heading" className="p-4">
      <h1 id="cover-heading" className="font-mono text-label uppercase text-muted">
        01&nbsp;&nbsp;COVER OVER TIME
      </h1>
      <p className="mt-2 font-mono text-label text-muted tabular-nums">{id}</p>
      <p className="mt-2 text-body text-secondary">
        One stacked bar per dive date, in the six reef colours.
      </p>
    </section>
  );
}
