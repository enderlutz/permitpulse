import { useEffect } from "react";
import { useWorkspace } from "@/store/workspace";
import { PageHeader } from "@/components/workspace/PageHeader";
import { WorkspaceGrid } from "@/components/workspace/WorkspaceGrid";

const PAGE = "submarkets";
const DEFAULT = {
  widgets: [
    { id: "hotspot-score", type: "hotspotScore", title: "Hotspot Ranking" },
    { id: "trending", type: "trendingZips", title: "Trending ZIPs" },
    { id: "trend", type: "volumeTrend", title: "Volume Trend" },
    { id: "type-mix", type: "typeMix", title: "Permit Type Mix" },
    { id: "map", type: "map", title: "ZIP Map" },
  ],
  layout: [
    { i: "hotspot-score", x: 0, y: 0, w: 5, h: 12, minW: 4, minH: 5 },
    { i: "trending", x: 5, y: 0, w: 3, h: 7, minW: 3, minH: 4 },
    { i: "trend", x: 8, y: 0, w: 4, h: 7, minW: 4, minH: 4 },
    { i: "type-mix", x: 5, y: 7, w: 3, h: 5, minW: 3, minH: 4 },
    { i: "map", x: 8, y: 7, w: 4, h: 5, minW: 3, minH: 4 },
  ],
};

export function SubmarketsPage() {
  const ws = useWorkspace((s) => s.byPage[PAGE]);
  const resetPage = useWorkspace((s) => s.resetPage);
  useEffect(() => {
    if (!ws) resetPage(PAGE, DEFAULT);
  }, [ws, resetPage]);
  return (
    <div className="flex h-full flex-col">
      <PageHeader page={PAGE} title="Submarkets" subtitle="Neighborhood and ZIP-level deep-dive" defaultLayout={() => resetPage(PAGE, DEFAULT)} />
      <div className="flex-1 overflow-auto">
        <WorkspaceGrid page={PAGE} />
      </div>
    </div>
  );
}
