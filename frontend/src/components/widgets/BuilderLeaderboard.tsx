import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { builderColor } from "@/lib/colors";
import { useWorkspace } from "@/store/workspace";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { BuilderDetailDrawer } from "./BuilderDetailDrawer";

type Tier = "national" | "local" | "individual";

const TIER_LABELS: Record<Tier, string> = {
  national: "National",
  local: "Local",
  individual: "Homeowners",
};

const TIER_BADGE_CLASSES: Record<Tier, string> = {
  national: "bg-primary/20 text-primary border-primary/30",
  local: "bg-secondary text-foreground/80 border-border",
  individual: "bg-muted text-muted-foreground border-border",
};

export function BuilderLeaderboard() {
  const period = useWorkspace((s) => s.filters.period);
  const builderFilter = useWorkspace((s) => s.filters.builder);
  const setFilter = useWorkspace((s) => s.setFilter);
  const [detailBuilder, setDetailBuilder] = useState<string | null>(null);

  // All three tiers visible by default. Homeowner permits aren't noise —
  // they're a market signal: ZIPs with heavy DIY activity hint at remodeling
  // demand and small-construction gig opportunities.
  const [enabled, setEnabled] = useState<Record<Tier, boolean>>({
    national: true,
    local: true,
    individual: true,
  });

  const activeTiers = (Object.keys(enabled) as Tier[]).filter((t) => enabled[t]);

  const { data, isLoading } = useQuery({
    queryKey: ["builders-leaderboard", period, activeTiers.join(",")],
    queryFn: () => api.builders.leaderboard(period, 10, activeTiers),
    enabled: activeTiers.length > 0,
  });

  const max = data?.[0]?.permit_count ?? 1;

  return (
    <div className="flex h-full flex-col gap-2">
      {/* Tier toggles */}
      <div className="flex flex-wrap items-center gap-1 border-b border-border pb-1.5">
        {(Object.keys(TIER_LABELS) as Tier[]).map((t) => (
          <button
            key={t}
            onClick={() => setEnabled((s) => ({ ...s, [t]: !s[t] }))}
            className={cn(
              "flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium transition-colors",
              enabled[t]
                ? TIER_BADGE_CLASSES[t]
                : "border-border bg-transparent text-muted-foreground/60 hover:text-foreground"
            )}
            title={enabled[t] ? `Hide ${TIER_LABELS[t].toLowerCase()}` : `Show ${TIER_LABELS[t].toLowerCase()}`}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", enabled[t] ? "bg-current" : "bg-current opacity-40")} />
            {TIER_LABELS[t]}
          </button>
        ))}
      </div>

      <BuilderDetailDrawer
        builder={detailBuilder}
        onClose={() => setDetailBuilder(null)}
      />

      {/* Leaderboard rows */}
      <div className="flex flex-1 flex-col gap-1 overflow-y-auto">
        {activeTiers.length === 0 ? (
          <div className="flex flex-1 items-center justify-center px-2 text-center text-[11px] text-muted-foreground">
            All tiers hidden — toggle one on above
          </div>
        ) : isLoading ? (
          Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-7 w-full" />)
        ) : data && data.length === 0 ? (
          <div className="flex flex-1 items-center justify-center text-xs text-muted-foreground">
            No builder data in period
          </div>
        ) : (
          data?.map((row) => {
            const pct = (row.permit_count / max) * 100;
            const active = builderFilter === row.builder;
            const tier = row.tier as Tier | null | undefined;
            return (
              <button
                key={row.builder}
                onClick={() => {
                  // Click a builder → show their permit pins on the map (and
                  // open the profile). Clicking the already-active builder
                  // clears the focus. The map reacts to filters.builder.
                  setDetailBuilder(row.builder);
                  setFilter("builder", active ? null : row.builder);
                }}
                className={cn(
                  "group relative flex items-center justify-between rounded px-2 py-1 text-left text-xs transition-colors hover:bg-secondary/60",
                  active && "bg-secondary"
                )}
                title={active ? "Click to clear this builder's map filter" : "Click to show this builder's permits on the map"}
              >
                <div
                  className="absolute inset-y-0 left-0 rounded bg-gradient-to-r opacity-15"
                  style={{
                    width: `${pct}%`,
                    backgroundImage: `linear-gradient(to right, ${builderColor(row.builder)}, transparent)`,
                  }}
                />
                <div className="relative flex min-w-0 flex-1 items-center gap-1.5">
                  <div className="h-2 w-2 shrink-0 rounded-full" style={{ background: builderColor(row.builder) }} />
                  <span className="truncate">{row.builder}</span>
                  {tier && tier !== "local" && (
                    <span
                      className={cn(
                        "shrink-0 rounded border px-1 text-[8px] uppercase tracking-wide",
                        TIER_BADGE_CLASSES[tier as Tier] ?? ""
                      )}
                    >
                      {tier === "national" ? "Nat'l" : tier === "individual" ? "DIY" : tier}
                    </span>
                  )}
                </div>
                <span className="num relative text-muted-foreground">{row.permit_count}</span>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
