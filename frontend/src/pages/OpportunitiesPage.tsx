import { useEffect } from "react";
import { useWorkspace } from "@/store/workspace";
import { PageHeader } from "@/components/workspace/PageHeader";
import { WorkspaceGrid } from "@/components/workspace/WorkspaceGrid";

const PAGE = "opportunities";
const DEFAULT = {
  widgets: [
    { id: "finder", type: "opportunities", title: "Opportunity Finder" },
    { id: "risk", type: "riskPulse", title: "Risk Pulse" },
    { id: "map", type: "map", title: "Opportunity Map" },
    { id: "digest", type: "aiDigest", title: "AI Digest" },
  ],
  layout: [
    { i: "finder", x: 0, y: 0, w: 6, h: 8, minW: 4, minH: 5 },
    { i: "risk", x: 6, y: 0, w: 6, h: 8, minW: 4, minH: 4 },
    { i: "map", x: 0, y: 8, w: 8, h: 8, minW: 6, minH: 5 },
    { i: "digest", x: 8, y: 8, w: 4, h: 8, minW: 3, minH: 4 },
  ],
};

export function OpportunitiesPage() {
  const ws = useWorkspace((s) => s.byPage[PAGE]);
  const resetPage = useWorkspace((s) => s.resetPage);
  useEffect(() => {
    if (!ws) resetPage(PAGE, DEFAULT);
  }, [ws, resetPage]);
  return (
    <div className="flex h-full flex-col">
      <PageHeader
        page={PAGE}
        title="Opportunities"
        subtitle="Surface gaps, emerging zones, and cooling markets"
        defaultLayout={() => resetPage(PAGE, DEFAULT)}
      />
      <div className="flex-1 overflow-auto">
        <WorkspaceGrid page={PAGE} />
      </div>
    </div>
  );
}
