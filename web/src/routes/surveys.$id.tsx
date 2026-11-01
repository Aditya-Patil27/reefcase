import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, dataOrNull } from "../api/client";
import type { components } from "../api/schema";
import { useEventStream } from "../live/useEventStream";
import { TracePanel } from "../components/TracePanel";
import { CaseFile, useCitedToolResults } from "../components/CaseFile";
import { AskCase } from "../components/AskCase";
import { EvidenceBody } from "../components/EvidenceBody";
import { SpecimenTray } from "../components/SpecimenTray";
import { PipelineSteps } from "../components/PipelineSteps";
import { EvidenceDrawer } from "../components/EvidenceDrawer";
import { useCrumb } from "../components/crumb";
import { BUTTON_PRIMARY } from "../components/marks";
import { formatCoordinates } from "../components/SitePicker";
import { toFrameView, type FrameView } from "../live/reducer";

type Investigation = components["schemas"]["Investigation"];
type Survey = components["schemas"]["Survey"];
type SiteDetail = components["schemas"]["SiteDetail"];
type EvidenceRef = components["schemas"]["EvidenceRef"];

export const Route = createFileRoute("/surveys/$id")({
  component: SurveyRouteComponent,
});

function computeStageIndex(
  reportReady: boolean,
  hasTools: boolean,
  hasAssessments: boolean,
  hasSegments: boolean,
  hasFrames: boolean,
): number {
  if (reportReady) return 5;
  if (hasTools) return 4;
  if (hasAssessments) return 3;
  if (hasSegments) return 2;
  if (hasFrames) return 1;
  return 0;
}

function SurveyRouteComponent() {
  const params = Route.useParams();
  const id = params.id;

  const { state, status, reconnectSeq } = useEventStream(id);
  const { setCrumb } = useCrumb();

  const [userEvidence, setUserEvidence] = useState<EvidenceRef | null>(null);
  const [lastFrameId, setLastFrameId] = useState<string>("");
  const [drawerOpen, setDrawerOpen] = useState(false);

  const investigationQuery = useQuery({
    queryKey: ["investigation", id],
    queryFn: async (): Promise<Investigation | null> => {
      const { data } = await api.GET("/api/surveys/{survey_id}/investigation", {
        params: { path: { survey_id: id } },
      });
      return data ?? null;
    },
    enabled: state.reportReady,
  });
  const investigation = investigationQuery.data;

  const surveyQuery = useQuery({
    queryKey: ["survey", id],
    queryFn: async (): Promise<Survey | null> => {
      const { data } = await api.GET("/api/surveys/{survey_id}", {
        params: { path: { survey_id: id } },
      });
      return data ?? null;
    },
  });
  const survey = surveyQuery.data;

  const siteQuery = useQuery({
    queryKey: ["site", survey?.site_id],
    queryFn: async (): Promise<SiteDetail | null> => {
      const { data } = await api.GET("/api/sites/{site_id}", {
        params: { path: { site_id: survey!.site_id } },
      });
      return data ?? null;
    },
    enabled: Boolean(survey?.site_id),
  });
  const site = siteQuery.data?.site;

  const historical = survey?.source === "historical";
  const framesQuery = useQuery({
    queryKey: ["frames", id],
    queryFn: async (): Promise<FrameView[]> => {
      const data = dataOrNull(
        await api.GET("/api/surveys/{survey_id}/frames", { params: { path: { survey_id: id } } }),
      );
      return (data ?? []).map((detail) => toFrameView(id, detail));
    },
    enabled: historical,
  });
  const frames = historical ? (framesQuery.data ?? []) : state.frames;

  const hasTools = state.toolCalls.length > 0 || state.findings.length > 0;
  const hasAssessments = state.frames.some((f) => f.assessment !== undefined);
  const hasSegments = state.frames.some((f) => f.cover !== undefined);
  const hasFrames = state.frames.length > 0;

  const currentStage = computeStageIndex(
    state.reportReady,
    hasTools,
    hasAssessments,
    hasSegments,
    hasFrames,
  );

  const { alert } = useCitedToolResults(investigation ?? undefined);

  const latestFrame = frames.length > 0 ? frames[frames.length - 1] : undefined;
  const selectedEvidence = userEvidence ?? (latestFrame ? { kind: "frame" as const, id: latestFrame.id } : null);
  const activeFrameId =
    (selectedEvidence?.kind === "frame" ? selectedEvidence.id : null) ??
    (lastFrameId || (latestFrame?.id ?? ""));

  // Update header crumb
  useEffect(() => {
    const parts = [
      site?.name,
      survey?.dive_date ? `Dive ${survey.dive_date}` : null,
      frames.length > 0 ? `${frames.length} frames` : null,
    ].filter(Boolean);
    if (parts.length > 0) {
      setCrumb(parts.join(" · "));
    }
    return () => setCrumb(null);
  }, [site?.name, survey?.dive_date, frames.length, setCrumb]);

  // Handle clicking citation keys or tool results
  const handleOpenEvidence = (ev: EvidenceRef) => {
    setUserEvidence(ev);
    if (ev.kind === "frame") {
      setLastFrameId(ev.id);
    }
    // Focus moves to stage heading
    const stage = document.getElementById("stage-region");
    stage?.focus();
  };

  // Collect cited frame IDs from investigation
  const citedFrameIds = new Set<string>();
  if (investigation) {
    for (const f of investigation.findings) {
      for (const e of f.evidence) {
        if (e.kind === "frame") citedFrameIds.add(e.id);
      }
    }
    for (const h of investigation.hypotheses) {
      for (const e of [...h.supporting, ...h.contradicting]) {
        if (e.kind === "frame") citedFrameIds.add(e.id);
      }
    }
  }

  const activeStageLabel = ["Upload", "Frames", "Segment", "Assess", "Investigate", "Report"][currentStage] ?? "Processing";

  return (
    <div className="flex flex-1 flex-col bg-bg text-ink">
      <header className="border-b border-rule bg-bg px-4 py-3 sm:px-10 flex flex-wrap items-baseline justify-between gap-4 md:sr-only">
        <h1 className="font-sans text-title font-bold text-ink">
          {site?.name ?? "Survey"}
        </h1>
        {site?.location ? (
          <p className="font-mono text-mono-sm text-mute">
            {formatCoordinates(site.location)}{survey?.dive_date ? ` · Dive ${survey.dive_date}` : ""}
          </p>
        ) : null}
      </header>

      {/* Historical banner if imported */}
      {historical ? (
        <div className="border-b border-rule bg-bg px-4 py-4 sm:px-10">
          <p className="font-sans text-ui font-semibold text-ink">
            Imported survey · segmented only, no investigation
          </p>
          <p className="mt-1 font-sans text-body text-mute">
            The frames were segmented when this record was imported. The agent never investigated the dive, so
            it has no case file and no trace.
          </p>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-12 px-4 py-6 sm:px-10 lg:grid-cols-[minmax(0,820px)_minmax(0,1fr)]">
        {/* Left Column: Pipeline Steps, Stage, Specimen Tray */}
        <section aria-labelledby="frames-heading" className="min-w-0 space-y-4 lg:self-start lg:top-4 lg:[@media(min-height:820px)]:sticky lg:[@media(min-height:820px)]:max-h-[calc(100dvh-2rem)] lg:[@media(min-height:820px)]:overflow-y-auto lg:[@media(min-height:820px)]:pb-1">
          <h2 id="frames-heading" className="sr-only">
            Frames
          </h2>

          {!historical ? (
            <PipelineSteps
              currentStage={currentStage}
              reportReady={state.reportReady}
              failed={state.failed}
            />
          ) : null}

          {/* Velvet Stage */}
          <div
            id="stage-region"
            tabIndex={-1}
            aria-label="Evidence stage"
            className="focus:outline-none"
          >
            <EvidenceBody
              evidence={selectedEvidence}
              frames={frames}
              surveyCover={survey?.cover}
              siteName={site?.name ?? "SITE"}
              diveDate={survey?.dive_date ?? ""}
              lat={site?.location?.lat}
              lon={site?.location?.lon}
              segBackend={historical ? "sam3" : undefined}
              mode="stage"
              onBackToFrame={() => {
                if (activeFrameId) {
                  setUserEvidence({ kind: "frame", id: activeFrameId });
                }
              }}
            />
          </div>

          {/* Specimen Tray */}
          <SpecimenTray
            frames={frames}
            selectedFrameId={activeFrameId}
            citedFrameIds={citedFrameIds}
            onSelectFrame={(frameId) => {
              setUserEvidence({ kind: "frame", id: frameId });
              setLastFrameId(frameId);
            }}
          />
        </section>

        {/* Right Column: Case File or Live Stream */}
        <section className="space-y-6">
          {state.reportReady && investigation ? (
            <div className="space-y-8">
              <CaseFile
                investigation={investigation}
                onOpenEvidence={handleOpenEvidence}
                frames={frames}
                toolCalls={state.toolCalls}
                alert={alert}
              />
              <AskCase
                surveyId={id}
                onOpenEvidence={handleOpenEvidence}
                frames={frames}
                toolCalls={state.toolCalls}
              />
            </div>
          ) : (
            <div className="space-y-6">
              {state.failed ? (
                <div role="alert" className="border-l-2 border-key-red pl-3.5 space-y-2">
                  <p className="font-sans text-ui font-semibold text-ink">
                    Stopped at {activeStageLabel}
                  </p>
                  <p className="font-sans text-body text-ink">
                    The run stopped: {state.failed}
                  </p>
                  <p className="font-sans text-body text-mute">
                    Nothing after {activeStageLabel.toLowerCase()} ran, so this dive has no case file. Upload the clip
                    again to start a fresh run.
                  </p>
                  <Link to="/upload" className={`${BUTTON_PRIMARY} mt-2`}>
                    Upload the clip again
                  </Link>
                </div>
              ) : null}

              {!historical ? (
                <TracePanel
                  toolCalls={state.toolCalls}
                  findings={state.findings}
                  stopped={Boolean(state.failed)}
                  status={status}
                  reconnectSeq={reconnectSeq}
                  frameIds={frames.map((f) => f.id)}
                  siteName={site?.name}
                  onSelectEvidence={(kind, evId) => handleOpenEvidence({ kind, id: evId })}
                />
              ) : null}
            </div>
          )}
        </section>
      </div>

      <EvidenceDrawer
        evidence={selectedEvidence}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        frames={frames}
      />
    </div>
  );
}
