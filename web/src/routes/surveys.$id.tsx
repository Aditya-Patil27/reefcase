import SegmentedControl from "../components/arc/segmented-control/segmented-control";
import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { useEventStream } from "../live/useEventStream";
import { FrameGrid } from "../components/FrameGrid";
import { TracePanel } from "../components/TracePanel";
import { CaseFile } from "../components/CaseFile";
import { EvidenceDrawer, type EvidenceItem } from "../components/EvidenceDrawer";
import { CopyButton } from "../components/arc/copy-button/copy-button";
import { Stepper, type StepperStep } from "../components/arc/stepper/stepper";
import { ResizablePanels, ResizablePanel } from "../components/arc/resizable-panels/resizable-panels";
import TextShimmer from "../components/arc/text-shimmer/text-shimmer";
import { formatCoordinates } from "../components/SitePicker";

type Investigation = components["schemas"]["Investigation"];
type Survey = components["schemas"]["Survey"];
type SiteDetail = components["schemas"]["SiteDetail"];

export const Route = createFileRoute("/surveys/$id")({
  component: SurveyRouteComponent,
});

const PIPELINE_STAGES: StepperStep[] = [
  { id: "upload", label: "Upload" },
  { id: "frames", label: "Frames" },
  { id: "segment", label: "Segment" },
  { id: "assess", label: "Assess" },
  { id: "investigate", label: "Investigate" },
  { id: "report", label: "Report" },
];

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

function useIsDesktop(breakpoint = 1280): boolean {
  const [isDesktop, setIsDesktop] = useState(
    typeof window !== "undefined" ? window.innerWidth >= breakpoint : true
  );

  useEffect(() => {
    const handleResize = () => setIsDesktop(window.innerWidth >= breakpoint);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [breakpoint]);

  return isDesktop;
}

function useElapsedTime(running: boolean): string {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => {
      setSeconds((s) => s + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [running]);

  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function SurveyRouteComponent() {
  const params = Route.useParams();
  const id = params.id;

  const { state, status, reconnectSeq } = useEventStream(id);
  const elapsed = useElapsedTime(!state.reportReady && !state.failed);
  const isDesktop = useIsDesktop(1280);

  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [viewMode, setViewMode] = useState<"report" | "frames">("report");

  const handleOpenEvidence = (ev: EvidenceItem) => {
    setSelectedEvidence(ev);
    setDrawerOpen(true);
  };

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

  const activeStageLabel = PIPELINE_STAGES[currentStage]?.label ?? "Processing";

  return (
    <div className="flex min-h-[calc(100vh-48px-32px)] flex-col bg-bg text-fg">
      {/* Header strip */}
      <header className="border-b border-hairline bg-surface px-4 py-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h1 className="text-title font-semibold text-fg">{site?.name ?? "Survey"}</h1>
            <span className="font-mono text-label text-secondary tabular-nums">
              {[site ? formatCoordinates(site.location) : null, survey?.dive_date]
                .filter(Boolean)
                .join(" · ")}
            </span>
            <span className="flex items-center gap-1 font-mono text-label text-muted">
              {id}
              <CopyButton value={id} iconOnly />
            </span>
          </div>

          <time className="font-mono text-label text-muted tabular-nums" aria-label="Elapsed time">
            {elapsed}
          </time>
        </div>

        {/* Stepper row */}
        <div className="mt-3 flex items-center justify-between gap-4">
          {/* Wide stepper */}
          <div className="hidden sm:block sm:flex-1">
            <Stepper
              steps={PIPELINE_STAGES}
              current={currentStage}
              className="w-full max-w-3xl"
            />
          </div>

          {/* Narrow collapsed stepper readout */}
          <div className="flex items-center gap-2 font-mono text-label text-secondary sm:hidden">
            <span>{`Stage ${currentStage + 1}/6 · `}</span>
            <span className="text-accent">
              <TextShimmer active={!state.reportReady}>{activeStageLabel}</TextShimmer>
            </span>
          </div>

          {/* Running status badge */}
          {!state.reportReady ? (
            <div className="hidden items-center gap-1 font-mono text-label text-accent sm:flex">
              <TextShimmer active>{activeStageLabel}</TextShimmer>
            </div>
          ) : (
            <span className="font-mono text-label text-success">Report ready</span>
          )}
        </div>
      </header>

      {/* Body: Wide ResizablePanels, narrow stacked */}
      {isDesktop ? (
        <div className="flex-1">
          <ResizablePanels label="Investigation panels" className="h-full min-h-[640px]">
            <ResizablePanel id="frames-panel" label="Frames" defaultSize={62} minSize={380}>
              <div className="h-full overflow-y-auto p-4">
                {state.reportReady && investigation ? (
                  <div className="space-y-4">
                    <SegmentedControl
                      options={[
                        { value: "report", label: "Case file" },
                        { value: "frames", label: "Frames" },
                      ]}
                      value={viewMode}
                      onValueChange={(val: string) => setViewMode(val as "report" | "frames")}
                    />
                    {viewMode === "report" ? (
                      <CaseFile
                        investigation={investigation}
                        onOpenEvidence={handleOpenEvidence}
                        frames={state.frames}
                        toolCalls={state.toolCalls}
                      />
                    ) : (
                      <FrameGrid frames={state.frames} />
                    )}
                  </div>
                ) : (
                  <FrameGrid frames={state.frames} />
                )}
              </div>
            </ResizablePanel>
            <ResizablePanel id="trace-panel" label="Trace" defaultSize={38} minSize={380}>
              <div className="h-full overflow-y-auto border-l border-hairline p-4">
                <TracePanel
                  toolCalls={state.toolCalls}
                  findings={state.findings}
                  status={status}
                  reconnectSeq={reconnectSeq}
                  frameIds={state.frames.map((f) => f.id)}
                  onSelectEvidence={(kind, evId) => handleOpenEvidence({ kind, id: evId })}
                />
              </div>
            </ResizablePanel>
          </ResizablePanels>
        </div>
      ) : (
        <div className="space-y-6 p-4">
          {state.reportReady && investigation ? (
            <div className="space-y-4">
              <SegmentedControl
                options={[
                  { value: "report", label: "Case file" },
                  { value: "frames", label: "Frames" },
                ]}
                value={viewMode}
                onValueChange={(val: string) => setViewMode(val as "report" | "frames")}
              />
              {viewMode === "report" ? (
                <CaseFile
                  investigation={investigation}
                  onOpenEvidence={handleOpenEvidence}
                  frames={state.frames}
                  toolCalls={state.toolCalls}
                />
              ) : (
                <FrameGrid frames={state.frames} />
              )}
            </div>
          ) : (
            <FrameGrid frames={state.frames} />
          )}
          <TracePanel
            toolCalls={state.toolCalls}
            findings={state.findings}
            status={status}
            reconnectSeq={reconnectSeq}
            frameIds={state.frames.map((f) => f.id)}
            onSelectEvidence={(kind, evId) => handleOpenEvidence({ kind, id: evId })}
          />
        </div>
      )}

      <EvidenceDrawer
        evidence={selectedEvidence}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        frames={state.frames}
      />
    </div>
  );
}
