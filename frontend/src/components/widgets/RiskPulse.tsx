import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, TrendingDown } from "lucide-react";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatPct } from "@/lib/utils";
import { useWorkspace } from "@/store/workspace";

export function RiskPulse() {
  const setFilter = useWorkspace((s) => s.setFilter);
  const { data, isLoading } = useQuery({
    queryKey: ["risk-pulse"],
    queryFn: () => api.opportunities.run("cooling-market", 10),
  });

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex items-center gap-1.5 rounded border border-amber-500/30 bg-amber-500/10 p-2 text-[11px] text-amber-200">
        <AlertTriangle className="h-3 w-3" />
        Markets cooling vs prior 5 months. Avoid or revisit pricing.
      </div>
      <div className="flex-1 space-y-1 overflow-auto pr-1">
        {isLoading
          ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)
          : data?.map((row) => (
              <button
                key={row.zip_code}
                onClick={() => setFilter("zip", row.zip_code)}
                className="flex w-full items-center justify-between rounded border border-border bg-surface/40 px-2 py-1.5 text-xs hover:bg-secondary/60"
              >
                <span className="num font-medium">{row.zip_code}</span>
                <div className="flex items-center gap-3 text-[10px]">
                  <span className="text-muted-foreground">
                    {row.recent_30d}/<span className="num">{row.expected}</span> exp
                  </span>
                  <span className={cn("num flex items-center gap-0.5 text-destructive")}>
                    <TrendingDown className="h-2.5 w-2.5" />
                    {formatPct(row.decel_pct, 0)}
                  </span>
                </div>
              </button>
            ))}
        {data && data.length === 0 && !isLoading && (
          <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
            No cooling markets detected — all submarkets stable or growing.
          </div>
        )}
      </div>
    </div>
  );
}
