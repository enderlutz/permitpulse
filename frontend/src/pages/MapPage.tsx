import { useEffect } from "react";
import { useWorkspace } from "@/store/workspace";
import { PageHeader } from "@/components/workspace/PageHeader";
import { WorkspaceGrid } from "@/components/workspace/WorkspaceGrid";

const PAGE = "map";
const DEFAULT = {
  widgets: [
    { id: "map-main", type: "map", title: "Permit Map" },
    { id: "trending", type: "trendingZips", title: "Trending ZIPs" },
    { id: "type-mix", type: "typeMix", title: "Permit Type Mix" },
    { id: "recent", type: "recentPermits", title: "Recent Permits" },
  ],
  layout: [
    { i: "map-main", x: 0, y: 0, w: 9, h: 15, minW: 6, minH: 8 },
    { i: "trending", x: 9, y: 0, w: 3, h: 7, minW: 3, minH: 4 },
    { i: "type-mix", x: 9, y: 7, w: 3, h: 8, minW: 3, minH: 4 },
    { i: "recent", x: 0, y: 15, w: 12, h: 5, minW: 6, minH: 4 },
  ],
};

export function MapPage() {
  const ws = useWorkspace((s) => s.byPage[PAGE]);
  const resetPage = useWorkspace((s) => s.resetPage);
  useEffect(() => {
    if (!ws) resetPage(PAGE, DEFAULT);
  }, [ws, resetPage]);
  return (
    <div className="flex h-full flex-col">
      <PageHeader page={PAGE} title="Map" subtitle="Full-bleed permit map exploration" defaultLayout={() => resetPage(PAGE, DEFAULT)} />
      <div className="flex-1 overflow-auto">
        <WorkspaceGrid page={PAGE} />
      </div>
    </div>
  );
}
