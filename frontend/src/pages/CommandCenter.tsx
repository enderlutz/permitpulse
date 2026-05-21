import { useEffect } from "react";
import { useWorkspace } from "@/store/workspace";
import { PageHeader } from "@/components/workspace/PageHeader";
import { WorkspaceGrid } from "@/components/workspace/WorkspaceGrid";

const PAGE = "command-center";
const DEFAULT = {
  widgets: [
    { id: "kpis-default", type: "kpis", title: "Market Snapshot" },
    { id: "map-default", type: "map", title: "Permit Map" },
    { id: "leaderboard-default", type: "builderLeaderboard", title: "Top Builders · 30d" },
    { id: "trending-default", type: "trendingZips", title: "Trending ZIPs" },
    { id: "recent-default", type: "recentPermits", title: "Recent Permits" },
    { id: "digest-default", type: "aiDigest", title: "AI Weekly Digest" },
    { id: "timelapse-default", type: "timelapse", title: "Time-lapse" },
  ],
  layout: [
    { i: "kpis-default", x: 0, y: 0, w: 12, h: 3, minW: 6, minH: 2 },
    { i: "map-default", x: 0, y: 3, w: 8, h: 10, minW: 4, minH: 6 },
    { i: "leaderboard-default", x: 8, y: 3, w: 4, h: 5, minW: 3, minH: 4 },
    { i: "trending-default", x: 8, y: 8, w: 4, h: 5, minW: 3, minH: 4 },
    { i: "recent-default", x: 0, y: 13, w: 4, h: 6, minW: 3, minH: 4 },
    { i: "digest-default", x: 4, y: 13, w: 5, h: 6, minW: 4, minH: 4 },
    { i: "timelapse-default", x: 9, y: 13, w: 3, h: 6, minW: 3, minH: 4 },
  ],
};

export function CommandCenter() {
  const ws = useWorkspace((s) => s.byPage[PAGE]);
  const resetPage = useWorkspace((s) => s.resetPage);

  useEffect(() => {
    if (!ws) resetPage(PAGE, DEFAULT);
  }, [ws, resetPage]);

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        page={PAGE}
        title="Command Center"
        subtitle="Market overview · the room you walk into"
        defaultLayout={() => resetPage(PAGE, DEFAULT)}
      />
      <div className="flex-1 overflow-auto">
        <WorkspaceGrid page={PAGE} />
      </div>
    </div>
  );
}
