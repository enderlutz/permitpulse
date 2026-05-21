import { useEffect } from "react";
import { useWorkspace } from "@/store/workspace";
import { PageHeader } from "@/components/workspace/PageHeader";
import { WorkspaceGrid } from "@/components/workspace/WorkspaceGrid";

const PAGE = "builders";
const DEFAULT = {
  widgets: [
    { id: "leaderboard", type: "builderLeaderboard", title: "Top Builders" },
    { id: "compare", type: "builderCompare", title: "Builder vs Builder" },
    { id: "map", type: "map", title: "Builder Footprint Map" },
    { id: "trend", type: "volumeTrend", title: "Volume Trend" },
  ],
  layout: [
    { i: "leaderboard", x: 0, y: 0, w: 3, h: 12, minW: 3, minH: 4 },
    { i: "compare", x: 3, y: 0, w: 5, h: 7, minW: 4, minH: 5 },
    { i: "map", x: 8, y: 0, w: 4, h: 12, minW: 3, minH: 6 },
    { i: "trend", x: 3, y: 7, w: 5, h: 5, minW: 4, minH: 4 },
  ],
};

export function BuildersPage() {
  const ws = useWorkspace((s) => s.byPage[PAGE]);
  const resetPage = useWorkspace((s) => s.resetPage);
  useEffect(() => {
    if (!ws) resetPage(PAGE, DEFAULT);
  }, [ws, resetPage]);
  return (
    <div className="flex h-full flex-col">
      <PageHeader
        page={PAGE}
        title="Builders"
        subtitle="Competitive intelligence on every active builder in Houston"
        defaultLayout={() => resetPage(PAGE, DEFAULT)}
      />
      <div className="flex-1 overflow-auto">
        <WorkspaceGrid page={PAGE} />
      </div>
    </div>
  );
}
