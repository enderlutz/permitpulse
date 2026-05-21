import { useEffect } from "react";
import { useWorkspace } from "@/store/workspace";
import { PageHeader } from "@/components/workspace/PageHeader";
import { WorkspaceGrid } from "@/components/workspace/WorkspaceGrid";

const PAGE = "watchlist";
const DEFAULT = {
  widgets: [
    { id: "watch", type: "watchlist", title: "Saved Items" },
    { id: "recent", type: "recentPermits", title: "Recent Activity" },
    { id: "map", type: "map", title: "Tracked Areas Map" },
  ],
  layout: [
    { i: "watch", x: 0, y: 0, w: 4, h: 10, minW: 3, minH: 5 },
    { i: "recent", x: 4, y: 0, w: 4, h: 10, minW: 3, minH: 4 },
    { i: "map", x: 8, y: 0, w: 4, h: 10, minW: 3, minH: 5 },
  ],
};

export function WatchlistPage() {
  const ws = useWorkspace((s) => s.byPage[PAGE]);
  const resetPage = useWorkspace((s) => s.resetPage);
  useEffect(() => {
    if (!ws) resetPage(PAGE, DEFAULT);
  }, [ws, resetPage]);
  return (
    <div className="flex h-full flex-col">
      <PageHeader
        page={PAGE}
        title="Watchlist"
        subtitle="Tracked ZIPs and builders · alerts on new activity"
        defaultLayout={() => resetPage(PAGE, DEFAULT)}
      />
      <div className="flex-1 overflow-auto">
        <WorkspaceGrid page={PAGE} />
      </div>
    </div>
  );
}
