import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/surveys/$id")({
  component: SurveyRoute,
});

/** Placeholder for the live investigation (6.3): a section label and the survey readout. */
function SurveyRoute() {
  const { id } = Route.useParams();

  return (
    <section aria-labelledby="frames-heading" className="p-4">
      <h1 id="frames-heading" className="font-mono text-label uppercase text-muted">
        01&nbsp;&nbsp;FRAMES
      </h1>
      <p className="mt-2 font-mono text-label text-muted tabular-nums">{id}</p>
      <p className="mt-2 text-body text-secondary">
        Frames arrive on the event stream in the order they are scored.
      </p>
    </section>
  );
}
