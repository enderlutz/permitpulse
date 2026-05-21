import { useQuery, useQueries } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { builderColor } from "@/lib/colors";
import { cn, formatNum } from "@/lib/utils";
import { useWorkspace } from "@/store/workspace";
import { Skeleton } from "@/components/ui/skeleton";

export function BuilderCompare() {
  const period = useWorkspace((s) => s.filters.period);
  const { data: leaderboard } = useQuery({
    queryKey: ["builders-all", period],
    queryFn: () => api.builders.leaderboard(period, 15),
  });

  const [selected, setSelected] = useState<string[]>([]);

  const footprints = useQueries({
    queries: selected.map((b) => ({
      queryKey: ["footprint", b, period],
      queryFn: () => api.builders.footprint(b, period),
    })),
  });

  const toggle = (b: string) => {
    setSelected((s) => (s.includes(b) ? s.filter((x) => x !== b) : s.length >= 3 ? [...s.slice(1), b] : [...s, b]));
  };

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Select up to 3</div>
      <div className="flex flex-wrap gap-1">
        {leaderboard?.slice(0, 10).map((b) => {
          const isSel = selected.includes(b.builder);
          return (
            <button
              key={b.builder}
              onClick={() => toggle(b.builder)}
              className={cn(
                "flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] transition-colors",
                isSel ? "ring-1 ring-primary" : "bg-secondary text-muted-foreground hover:text-foreground"
              )}
              style={isSel ? { background: `${builderColor(b.builder)}30`, color: builderColor(b.builder) } : undefined}
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: builderColor(b.builder) }} />
              {b.builder}
              <span className="num text-[10px] opacity-60">{b.permit_count}</span>
            </button>
          );
        })}
      </div>
      <div className="flex-1 overflow-auto pr-1">
        {selected.length === 0 && (
          <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
            Pick builders above to compare footprints
          </div>
        )}
        <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${Math.max(1, selected.length)}, minmax(0, 1fr))` }}>
          {selected.map((b, i) => {
            const fp = footprints[i].data;
            const loading = footprints[i].isLoading;
            return (
              <div key={b} className="rounded-md border border-border bg-surface/60 p-2">
                <div className="mb-1 flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: builderColor(b) }} />
                  <span className="truncate text-xs font-semibold">{b}</span>
                </div>
                {loading ? (
                  <Skeleton className="h-20 w-full" />
                ) : (
                  <>
                    <div className="num text-lg font-semibold">{formatNum(fp?.permit_count ?? 0)}</div>
                    <div className="text-[10px] text-muted-foreground">permits in {period}</div>
                    <div className="mt-1.5 space-y-0.5">
                      {fp?.zip_codes?.slice(0, 5).map(([z, n]: any) => (
                        <div key={z} className="flex items-center justify-between text-[10px]">
                          <span className="num">{z}</span>
                          <span className="num text-muted-foreground">{n}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
