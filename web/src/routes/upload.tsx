import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/upload")({
  component: UploadRoute,
});

/** Placeholder for the upload form (6.2): a section label and one line of real copy. */
function UploadRoute() {
  return (
    <section aria-labelledby="clip-heading" className="p-4">
      <h1 id="clip-heading" className="font-mono text-label uppercase text-muted">
        01&nbsp;&nbsp;CLIP
      </h1>
      <p className="mt-2 text-body text-secondary">
        A dive clip, its site and its dive date start an investigation.
      </p>
    </section>
  );
}
