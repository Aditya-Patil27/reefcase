import type { ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import { Drawer, DrawerContent } from "./arc/drawer/drawer";
import { EvidenceBody } from "./EvidenceBody";
import { api, dataOrNull } from "../api/client";
import type { components } from "../api/schema";
import type { FrameView } from "../live/reducer";
import { frameLabel, humanize } from "../format";

export type EvidenceRef = components["schemas"]["EvidenceRef"];
export type EvidenceItem = EvidenceRef;
type ToolResult = components["schemas"]["ToolResult"];

export interface EvidenceDrawerProps {
  evidence: EvidenceRef | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  frames?: FrameView[];
}

async function fetchToolResult(id: string): Promise<ToolResult | null> {
  return dataOrNull(
    await api.GET("/api/tool-results/{tool_result_id}", {
      params: { path: { tool_result_id: id } },
    }),
  );
}

export function EvidenceDrawer({
  evidence,
  open,
  onOpenChange,
  frames = [],
}: EvidenceDrawerProps): ReactElement {
  const toolQuery = useQuery({
    queryKey: ["tool_result", evidence?.id],
    queryFn: () => (evidence?.id ? fetchToolResult(evidence.id) : null),
    enabled: evidence?.kind === "tool_result" && Boolean(evidence.id),
  });

  const frameIds = frames.map((f) => f.id);
  const frameName = evidence?.kind === "frame" ? frameLabel(frameIds, evidence.id) : "";
  const toolResult = toolQuery.data;

  const title =
    evidence?.kind === "frame"
      ? frameName
      : toolResult
        ? humanize(toolResult.tool)
        : "Evidence item";

  const description =
    evidence?.kind === "frame"
      ? "Transect frame and its segmentation mask"
      : toolResult
        ? `Retrieved ${toolResult.retrieved_at.slice(0, 16).replace("T", " ")} UTC`
        : "Investigation evidence";

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent
        title={title}
        description={description}
        side="right"
        className="evidence-drawer h-full w-full overflow-y-auto border-l border-rule bg-bg p-6 text-ink sm:max-w-[480px]"
      >
        <div className="pt-4">
          <EvidenceBody
            evidence={evidence}
            frames={frames}
            mode="drawer"
          />
        </div>
      </DrawerContent>
    </Drawer>
  );
}
