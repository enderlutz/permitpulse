import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn, formatPct, formatNum } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { useWorkspace } from "@/store/workspace";
import { Lightbulb } from "lucide-react";

export function OpportunityFinder() {
  const setFilter = useWorkspace((s) => s.setFilter);
  const { data: presets } = useQuery({ queryKey: ["op-presets"], queryFn: () => api.opportunities.presets() });
  const [activeId, setActiveId] = useState<string>("small-builder-gap");

  const { data: results, isFetching } = useQuery({
    queryKey: ["op-run", activeId],
    queryFn: () => api.opportunities.run(activeId, 10),
    enabled: !!activeId,
  });

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex flex-wrap gap-1">
        {presets?.map((p) => (
          <button
            key={p.id}
            onClick={() => setActiveId(p.id)}
            className={cn(
              "rounded-md px-2 py-1 text-[11px] transition-colors",
              activeId === p.id ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground"
            )}
          >
            {p.name}
          </button>
        ))}
      </div>
      {presets?.find((p) => p.id === activeId)?.description && (
        <p className="flex items-start gap-1.5 rounded border border-border bg-surface/60 p-2 text-[11px] text-muted-foreground">
          <Lightbulb className="mt-0.5 h-3 w-3 shrink-0 text-amber-400" />
          {presets.find((p) => p.id === activeId)?.description}
        </p>
      )}
      <div className="flex-1 space-y-1 overflow-auto pr-1">
        {isFetching && Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
        {results?.map((row, i) => (
          <button
            key={i}
            onClick={() => setFilter("zip", row.zip_code)}
            className="flex w-full items-center justify-between gap-2 rounded border border-border bg-surface/40 px-2.5 py-1.5 text-left text-xs hover:bg-secondary/60"
          >
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="num text-[10px]">{i + 1}</Badge>
              <span className="num font-medium">{row.zip_code}</span>
            </div>
            <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
              {activeId === "small-builder-gap" && (
                <>
                  <span>big: <span className="num text-foreground">{row.big_builder_permits}</span></span>
                  <span>small: <span className="num text-foreground">{row.small_builder_permits}</span></span>
                </>
              )}
              {activeId === "emerging-velocity" && (
                <>
                  <span>30d: <span className="num text-foreground">{formatNum(row.recent_30d)}</span></span>
                  <span className="num text-primary">{formatPct(row.velocity_pct, 0)}</span>
                </>
              )}
              {activeId === "cooling-market" && (
                <>
                  <span>recent: <span className="num text-foreground">{row.recent_30d}</span></span>
                  <span>exp: <span className="num text-foreground">{row.expected}</span></span>
                  <span className="num text-destructive">{formatPct(row.decel_pct, 0)}</span>
                </>
              )}
              {activeId === "commercial-residential-divergence" && (
                <>
                  <span>comm: <span className="num text-foreground">{row.commercial}</span></span>
                  <span>res: <span className="num text-foreground">{row.residential}</span></span>
                </>
              )}
            </div>
          </button>
        ))}
        {results && results.length === 0 && !isFetching && (
          <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
            No matches — try a different preset or widen the period.
          </div>
        )}
      </div>
    </div>
  );
}
