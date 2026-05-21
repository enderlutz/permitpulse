import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useWorkspace } from "@/store/workspace";
import { formatPct, formatNum, cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { Flame } from "lucide-react";

export function HotspotScore() {
  const period = useWorkspace((s) => s.filters.period);
  const setFilter = useWorkspace((s) => s.setFilter);
  const zip = useWorkspace((s) => s.filters.zip);
  const { data, isLoading } = useQuery({
    queryKey: ["hotspots-score", period],
    queryFn: () => api.analytics.hotspots(period, 15),
  });

  return (
    <div className="flex h-full flex-col">
      <div className="mb-1 grid grid-cols-[auto_1fr_auto_auto] gap-2 px-2 text-[10px] uppercase tracking-wider text-muted-foreground">
        <span>ZIP</span>
        <span>Score</span>
        <span className="text-right">Vol</span>
        <span className="text-right">Vel</span>
      </div>
      <div className="flex-1 space-y-0.5 overflow-auto pr-1">
        {isLoading
          ? Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} className="h-7 w-full" />)
          : data?.map((row) => {
              const active = zip === row.zip_code;
              return (
                <button
                  key={row.zip_code}
                  onClick={() => setFilter("zip", active ? null : row.zip_code)}
                  className={cn(
                    "grid w-full grid-cols-[auto_1fr_auto_auto] items-center gap-2 rounded px-2 py-1.5 text-xs transition-colors hover:bg-secondary/60",
                    active && "bg-secondary"
                  )}
                >
                  <span className="num font-medium">{row.zip_code}</span>
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-secondary">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-amber-400 to-emerald-400"
                        style={{ width: `${Math.min(100, row.score)}%` }}
                      />
                    </div>
                    <span className="num shrink-0 text-[10px] text-muted-foreground">{row.score.toFixed(0)}</span>
                  </div>
                  <span className="num text-right text-muted-foreground">{formatNum(row.permit_count)}</span>
                  <span
                    className={cn(
                      "num text-right text-[10px]",
                      row.velocity_pct >= 0 ? "text-primary" : "text-destructive"
                    )}
                  >
                    {formatPct(row.velocity_pct, 0)}
                  </span>
                </button>
              );
            })}
      </div>
      <div className="mt-1 flex items-center justify-between border-t border-border pt-1.5 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <Flame className="h-2.5 w-2.5" /> Score = 60% volume + 30% velocity + 10% recency
        </span>
        <span className="num">{data?.length ?? 0} ranked</span>
      </div>
    </div>
  );
}
