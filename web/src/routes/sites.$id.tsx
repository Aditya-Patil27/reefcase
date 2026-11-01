import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState, type CSSProperties } from "react";
import { api, dataOrNull } from "../api/client";
import type { components } from "../api/schema";
import { formatCoordinates } from "../components/SitePicker";
import { CoverChart } from "../components/CoverChart";
import { CoverStrip } from "../components/CoverStrip";
import { EvidenceDrawer } from "../components/EvidenceDrawer";
import { SpecimenLabel } from "../components/SpecimenLabel";
import { SpecimenTray } from "../components/SpecimenTray";
import { SortableDataTable, type DataColumn } from "../components/arc/sortable-data-table/sortable-data-table";
import { BUTTON_PRIMARY, BUTTON_SECONDARY, TEXT_LINK } from "../components/marks";
import { causeLabel, formatSignedPp, splitFirstSentence, frameLabel } from "../format";
import { toFrameView, type FrameView } from "../live/reducer";
import { useCrumb } from "../components/crumb";

type SiteDetail = components["schemas"]["SiteDetail"];
type Survey = components["schemas"]["Survey"];
type Investigation = components["schemas"]["Investigation"];
type EvidenceRef = components["schemas"]["EvidenceRef"];

export const Route = createFileRoute("/sites/$id")({
  component: SiteRoute,
});

/**
 * The site title is 56px, but the 330px column (274px of text) must hold its longest word whole,
 * or "Lakshadweep" breaks mid-word. Extrabold glyphs average about 0.62em wide.
 */
function siteTitleStyle(name: string): CSSProperties | undefined {
  const longest = Math.max(...name.split(/\s+/).map((word) => word.length));
  const px = Math.floor(270 / (longest * 0.62));
  return px < 56 ? { fontSize: `${Math.max(px, 28)}px`, lineHeight: 1.05 } : undefined;
}

function percent(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}

function SiteRoute() {
  const { id } = Route.useParams();
  const [openedId, setOpenedId] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<EvidenceRef | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const siteQuery = useQuery({
    queryKey: ["site", id],
    queryFn: async (): Promise<SiteDetail | null> => {
      return dataOrNull(
        await api.GET("/api/sites/{site_id}", { params: { path: { site_id: id } } }),
      );
    },
  });

  const site = siteQuery.data?.site;
  useCrumb(site?.name ? site.name.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 8) : undefined);

  const surveys = siteQuery.data?.surveys ?? [];

  // A survey still running (or failed) has no cover yet and must not read as 0% live coral.
  const covered = surveys
    .filter((survey) => survey.cover)
    .sort((a, b) => a.dive_date.localeCompare(b.dive_date));
  const latest = covered[covered.length - 1];
  // The headline change is against the dive before the latest: what this dive found.
  const previous = covered.filter((survey) => survey.dive_date < (latest?.dive_date ?? "")).pop();
  // The evidence board shows the latest dive that came with footage.
  const evidenceSurvey = covered.filter((survey) => survey.video_path).pop() ?? latest;

  const framesQuery = useQuery({
    queryKey: ["frames", evidenceSurvey?.id],
    queryFn: async (): Promise<FrameView[]> => {
      const surveyId = evidenceSurvey!.id;
      const data = dataOrNull(
        await api.GET("/api/surveys/{survey_id}/frames", {
          params: { path: { survey_id: surveyId } },
        }),
      );
      return (data ?? []).map((detail) => toFrameView(surveyId, detail));
    },
    enabled: Boolean(evidenceSurvey),
  });

  const investigationQuery = useQuery({
    queryKey: ["investigation", evidenceSurvey?.id],
    queryFn: async (): Promise<Investigation | null> => {
      return dataOrNull(
        await api.GET("/api/surveys/{survey_id}/investigation", {
          params: { path: { survey_id: evidenceSurvey!.id } },
        }),
      );
    },
    enabled: Boolean(evidenceSurvey),
  });

  const frames = framesQuery.data ?? [];
  const investigation = investigationQuery.data ?? undefined;
  const [verdictFirst] = investigation ? splitFirstSentence(investigation.verdict) : ["", ""];
  const topHypothesis = investigation?.hypotheses
    ? [...investigation.hypotheses].sort((a, b) => b.confidence - a.confidence)[0]
    : undefined;

  // Until a reader opens one, the most bleached frame is the one under the strobe.
  const worst = frames.reduce<FrameView | undefined>(
    (best, f) =>
      f.cover && f.cover.bleached_coral > (best?.cover?.bleached_coral ?? -1) ? f : best,
    undefined,
  );
  const litId = openedId ?? worst?.id;
  const frameIds = frames.map((f) => f.id);
  const selectedFrameIndex = frames.findIndex((f) => f.id === litId);
  const selectedFrame = selectedFrameIndex >= 0 ? frames[selectedFrameIndex] : frames[0];

  function openEvidence(ref: EvidenceRef) {
    if (ref.kind === "frame") setOpenedId(ref.id);
    setEvidence(ref);
    setDrawerOpen(true);
  }

  const latestLive = latest?.cover?.live_coral ?? 0;
  const previousLive = previous?.cover?.live_coral ?? 0;

  const columns: DataColumn<Survey & Record<string, unknown>>[] = [
    {
      key: "dive_date",
      label: "Date",
      sortable: true,
      render: (_, row) => <span className="font-mono text-mono-base text-ink">{row.dive_date}</span>,
    },
    {
      key: "live_cover",
      label: "Live cover",
      sortable: true,
      numeric: true,
      render: (_, row) => (
        <span className="font-mono text-mono-base font-semibold text-ink">
          {row.cover ? percent(row.cover.live_coral) : "—"}
        </span>
      ),
    },
    {
      key: "cover",
      label: "Cover composition",
      render: (_, row) =>
        row.cover ? (
          <div className="w-36 py-1 sm:w-56">
            <CoverStrip cover={row.cover} className="h-2" />
          </div>
        ) : null,
    },
    {
      key: "actions",
      label: "",
      render: (_, row) => (
        <Link to="/surveys/$id" params={{ id: row.id }} className={`${TEXT_LINK} font-mono text-mono-sm whitespace-nowrap`}>
          Case file
        </Link>
      ),
    },
  ];

  const evidenceYear = evidenceSurvey?.dive_date.slice(0, 4);

  return (
    <div className="text-ink">
      <div className="grid border-b border-rule lg:grid-cols-[330px_minmax(0,1fr)] xl:grid-cols-[330px_minmax(0,1fr)_440px]">
        <aside aria-label="Site" className="space-y-6 border-rule px-4 py-7 sm:px-7 lg:border-r">
          <header className="space-y-2">
            <h1
              className="font-sans text-display font-bold break-words text-ink"
              style={siteTitleStyle(site?.name ?? "Site")}
            >
              {site?.name ?? "Site"}
            </h1>
            {site?.location ? (
              <p className="font-mono text-mono-sm text-mute">{formatCoordinates(site.location)}</p>
            ) : null}
            {site?.mpa_id ? (
              <span className="inline-block border border-rule bg-ground px-2 py-0.5 font-mono text-mono-eyebrow uppercase tracking-wider text-ink">
                MPA protected
              </span>
            ) : null}
          </header>

          {latest ? (
            <div aria-label="Site key figures" className="space-y-2">
              <p className="flex items-baseline gap-2">
                <span className="font-sans text-figure-lg font-bold tracking-tight text-ink">{percent(latestLive)}</span>{" "}
                <span className="font-sans text-ui text-mute">live coral</span>
              </p>{" "}
              <p className="font-mono text-mono-sm text-mute">
                {previous ? (
                  <>
                    <span className="font-semibold text-ink">
                      {formatSignedPp((latestLive - previousLive) * 100)} since{" "}
                      {previous.dive_date.slice(0, 4)}
                    </span>{" "}
                    ·{" "}
                  </>
                ) : null}
                {surveys.length} {surveys.length === 1 ? "survey" : "surveys"} · latest dive{" "}
                {latest.dive_date}
              </p>
            </div>
          ) : null}
        </aside>

        <section aria-label="Evidence" className="min-w-0 px-4 py-7 sm:px-7">
          {siteQuery.isPending ? (
            <p className="font-mono text-mono-sm text-mute">Loading the site record…</p>
          ) : siteQuery.isError ? (
            <p role="alert" className="font-sans text-body text-ink">
              The site record did not load. Check the API and reload the page.
            </p>
          ) : surveys.length === 0 ? (
            <div aria-label="No surveys recorded" className="max-w-md space-y-4">
              <p className="font-sans text-title font-bold text-ink">No dives yet</p>
              <p className="font-sans text-body text-mute">
                No surveys at this site yet. Upload a dive to start its record.
              </p>
              <Link to="/upload" className={BUTTON_PRIMARY}>
                Upload a dive
              </Link>
            </div>
          ) : framesQuery.isPending ? (
            <p className="font-mono text-mono-sm text-mute">Loading frames from the {evidenceYear} dive…</p>
          ) : framesQuery.isError ? (
            <p role="alert" className="font-sans text-body text-ink">
              The frames for the {evidenceYear} dive did not load. Reload the page to try again.
            </p>
          ) : frames.length === 0 ? (
            <div className="max-w-md space-y-2">
              <p className="font-sans text-title font-bold text-ink">No frames for the {evidenceYear} dive</p>
              <p className="font-sans text-body text-mute">
                This survey carries cover figures only. Upload footage from the site to see its
                frames here.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <h2 id="evidence-heading" className="font-mono text-mono-eyebrow uppercase tracking-wider text-mute">
                Evidence: {frames.length} {frames.length === 1 ? "frame" : "frames"} from the {evidenceYear} dive
              </h2>
              <div className="space-y-3">
                <div className="relative aspect-video max-h-[420px] w-full overflow-hidden bg-stage-bg text-stage-fg">
                  {selectedFrame ? (
                    <>
                      <img
                        src={selectedFrame.imageUrl ?? selectedFrame.thumbUrl}
                        alt={`${frameLabel(frameIds, selectedFrame.id)} stage`}
                        className="size-full object-contain"
                      />
                      <SpecimenLabel
                        siteName={site?.name ?? "SITE"}
                        diveDate={evidenceSurvey?.dive_date ?? ""}
                        frameIndex={selectedFrameIndex >= 0 ? selectedFrameIndex + 1 : 1}
                        frame={selectedFrame}
                        lat={site?.location?.lat}
                        lon={site?.location?.lon}
                      />
                    </>
                  ) : null}
                </div>
                <SpecimenTray
                  frames={frames}
                  selectedFrameId={litId}
                  onSelectFrame={(frameId) => {
                    setOpenedId(frameId);
                    openEvidence({ kind: "frame", id: frameId });
                  }}
                />
              </div>
            </div>
          )}
        </section>

        <aside
          aria-label="Latest case file"
          className="min-w-0 space-y-6 border-t border-rule bg-ground px-4 py-7 sm:px-7 lg:col-span-2 xl:col-span-1 xl:border-t-0 xl:border-l"
        >
          {siteQuery.isPending ? (
            <p className="font-mono text-mono-sm text-mute">Reading the case file…</p>
          ) : siteQuery.isError ? null : !evidenceSurvey ? (
            <p className="font-sans text-body text-mute">
              A case file appears here once a dive at this site has been investigated.
            </p>
          ) : investigationQuery.isPending ? (
            <p className="font-mono text-mono-sm text-mute">Reading the case file…</p>
          ) : investigationQuery.isError ? (
            <p role="alert" className="font-sans text-body text-ink">
              The case file for the {evidenceYear} dive did not load. Reload the page to try again.
            </p>
          ) : investigation ? (
            <div className="space-y-6">
              <h2
                className={
                  verdictFirst.length > 120
                    ? "max-w-[60ch] font-sans text-title font-bold text-ink"
                    : "font-sans text-verdict font-bold text-ink leading-tight"
                }
              >
                {verdictFirst}
              </h2>
              {topHypothesis ? (
                <div className="space-y-2">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-sans text-hyp-2 font-semibold text-ink">{causeLabel(topHypothesis.cause)}</span>
                    <span className="font-mono text-mono-base font-bold text-ink">
                      {Math.round(topHypothesis.confidence * 100)}%
                    </span>
                  </div>
                  <div className="h-1 w-full bg-rule">
                    <div
                      className="h-full bg-ink"
                      style={{ width: `${Math.round(topHypothesis.confidence * 100)}%` }}
                    />
                  </div>
                </div>
              ) : null}
              <div>
                <Link to="/surveys/$id" params={{ id: evidenceSurvey.id }} className={BUTTON_PRIMARY}>
                  Open full case file
                </Link>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="font-sans text-title font-bold text-ink">No case file for the {evidenceYear} dive</p>
              <p className="font-sans text-body text-mute">
                The agent has not investigated this dive yet.
              </p>
              <Link to="/surveys/$id" params={{ id: evidenceSurvey.id }} className={BUTTON_SECONDARY}>
                Open the dive
              </Link>
            </div>
          )}
        </aside>
      </div>

      {covered.length > 0 ? (
        <div className="space-y-12 px-4 py-10 sm:px-7">
          <section aria-labelledby="cover-heading" className="space-y-4">
            <h2 id="cover-heading" className="font-mono text-mono-eyebrow uppercase tracking-wider text-mute">
              Cover over time
            </h2>
            <CoverChart surveys={surveys} />
          </section>

          <section aria-labelledby="surveys-heading" className="space-y-4">
            <h2 id="surveys-heading" className="font-mono text-mono-eyebrow uppercase tracking-wider text-mute">
              Surveys
            </h2>
            <div className="max-w-full overflow-x-auto border-y border-rule">
              <SortableDataTable
                rows={covered.slice().reverse() as (Survey & Record<string, unknown>)[]}
                columns={columns}
                rowKey="id"
                caption="Recorded site surveys"
              />
            </div>
          </section>
        </div>
      ) : null}

      <EvidenceDrawer
        evidence={evidence}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        frames={frames}
      />
    </div>
  );
}
