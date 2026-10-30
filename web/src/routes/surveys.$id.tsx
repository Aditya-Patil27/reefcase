import SegmentedControl from "../components/arc/segmented-control/segmented-control";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, dataOrNull } from "../api/client";
import type { components } from "../api/schema";
import { useEventStream } from "../live/useEventStream";
import { FrameGrid } from "../components/FrameGrid";
import { TracePanel } from "../components/TracePanel";
import { CaseFile, useCitedToolResults } from "../components/CaseFile";
import { BUTTON_PRIMARY, CHIP, RULE_CITED } from "../components/strobe";
import { toFrameView, type FrameView } from "../live/reducer";
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
  const elapsed = useElapsedTime(!state.reportReady && !state.failed && status !== "closed");
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

  // An imported record was only ever segmented, so its frames come from the API, not the event stream.
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

  const activeStageLabel = PIPELINE_STAGES[currentStage]?.label ?? "Processing";
  // A failed run stops at the stage that was in progress.
  const stepperSteps = state.failed
    ? PIPELINE_STAGES.map((stage, i) => (i === currentStage ? { ...stage, error: "Stopped here" } : stage))
    : PIPELINE_STAGES;
  const { alert } = useCitedToolResults(investigation ?? undefined);

  // The frame under the strobe: the one just opened as evidence, else the most bleached.
  const openedFrameId = selectedEvidence?.kind === "frame" ? selectedEvidence.id : undefined;
  const mostBleached = frames.reduce<FrameView | undefined>(
    (worst, f) =>
      f.cover && f.cover.bleached_coral > (worst?.cover?.bleached_coral ?? -1) ? f : worst,
    undefined,
  );
  const litId = openedFrameId ?? mostBleached?.id;

  let framesDescription: string;
  if (historical) {
    framesDescription = framesQuery.isPending
      ? "Loading the frames from this dive…"
      : framesQuery.isError
        ? "The frames for this dive did not load. Reload the page to try again."
        : frames.length === 0
          ? "This record came without frames."
          : "Frames from the imported record, each with its segmentation mask. Open one to see it in true colour.";
  } else {
    framesDescription = hasFrames
      ? "Frames arrive as the clip is sampled. Open one to see it in true colour with its SAM 3 mask."
      : state.failed
        ? "No frames were read before the run stopped."
        : "Waiting for the first frame from the clip…";
  }

  const frameGrid = (
    <FrameGrid
      frames={frames}
      litId={litId}
      onOpenFrame={(frameId) => handleOpenEvidence({ kind: "frame", id: frameId })}
      description={framesDescription}
    />
  );

  const work =
    state.reportReady && investigation ? (
      <div className="space-y-5">
        <SegmentedControl
          label="Show"
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
            alert={alert}
          />
        ) : (
          frameGrid
        )}
      </div>
    ) : (
      frameGrid
    );

  const trace = (
    <TracePanel
      toolCalls={state.toolCalls}
      // Once the case file is ready it owns the findings; Trace keeps the tool calls.
      findings={state.reportReady ? [] : state.findings}
      stopped={Boolean(state.failed)}
      status={status}
      reconnectSeq={reconnectSeq}
      frameIds={state.frames.map((f) => f.id)}
      onSelectEvidence={(kind, evId) => handleOpenEvidence({ kind, id: evId })}
    />
  );

  return (
    <div className="flex flex-1 flex-col bg-bg text-fg">
      <header className="border-b border-hairline bg-surface px-4 py-5 sm:px-7">
        <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
          <div className="min-w-0 space-y-1">
            <h1 className="text-display font-extrabold text-fg">{site?.name ?? "Survey"}</h1>
            <p className="flex flex-wrap items-center gap-x-2 text-label text-secondary tabular-nums">
              {site ? <span>{formatCoordinates(site.location)}</span> : null}
              {survey?.dive_date ? <span>Dive {survey.dive_date}</span> : null}
              <span className="flex items-center gap-1">
                {id}
                <CopyButton value={id} iconOnly />
              </span>
            </p>
          </div>

          <div role="status" className="flex items-center gap-3 text-ui">
            {historical ? (
              <span className={CHIP}>Imported record</span>
            ) : state.failed ? (
              <span className="font-bold text-fg">Stopped at {activeStageLabel}</span>
            ) : state.reportReady ? (
              <span className={CHIP}>Case file ready</span>
            ) : (
              <>
                <span className="font-bold text-fg">
                  <TextShimmer active>{activeStageLabel}</TextShimmer>
                </span>
                <span className="text-label text-secondary sm:hidden">
                  Stage {currentStage + 1} of {PIPELINE_STAGES.length}
                </span>
              </>
            )}
            {state.failed || historical ? null : (
              <time className="text-label font-bold text-secondary tabular-nums" aria-label="Elapsed time">
                {elapsed}
              </time>
            )}
          </div>
        </div>

        {historical ? (
          <div className="mt-4 max-w-3xl">
            <p className="text-ui font-bold text-fg">Imported survey · segmented only, no investigation</p>
            <p className="mt-1 text-body text-secondary">
              The frames were segmented when this record was imported. The agent never investigated the dive, so
              it has no case file and no trace.
            </p>
          </div>
        ) : (
          <div className="mt-4 hidden sm:block">
            {/* A stopped stage is not a proven alert, so the stepper's error mark draws in deep, not red. */}
            <Stepper steps={stepperSteps} current={currentStage} className="w-full max-w-3xl [--danger:var(--deep)]" />
          </div>
        )}

        {state.failed ? (
          <div role="alert" className={`mt-5 max-w-3xl ${RULE_CITED}`}>
            <p className="text-ui font-bold text-fg">The run stopped: {state.failed}</p>
            <p className="mt-1 text-body text-secondary">
              Nothing after {activeStageLabel.toLowerCase()} ran, so this dive has no case file. Upload the clip
              again to start a fresh run.
            </p>
            <Link to="/upload" className={`${BUTTON_PRIMARY} mt-4`}>
              Upload the clip again
            </Link>
          </div>
        ) : null}
      </header>

      {historical ? (
        <div className="px-4 py-6 sm:px-7">{frameGrid}</div>
      ) : isDesktop ? (
        <div className="flex-1">
          <ResizablePanels label="Investigation panels" className="h-full min-h-[640px]">
            <ResizablePanel id="frames-panel" label="Frames" defaultSize={62} minSize={380}>
              <div className="h-full overflow-y-auto px-7 py-6">{work}</div>
            </ResizablePanel>
            <ResizablePanel id="trace-panel" label="Trace" defaultSize={38} minSize={380}>
              <div className="h-full overflow-y-auto border-l border-hairline bg-surface px-6 py-6">
                {trace}
              </div>
            </ResizablePanel>
          </ResizablePanels>
        </div>
      ) : (
        <div className="space-y-10 px-4 py-6 sm:px-7">
          {work}
          <div className="border-t border-hairline pt-6">{trace}</div>
        </div>
      )}

      <EvidenceDrawer
        evidence={selectedEvidence}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        frames={frames}
      />
    </div>
  );
}
