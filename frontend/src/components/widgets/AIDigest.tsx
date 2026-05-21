import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

// Compose a narrative client-side from real KPIs + hotspots + builder leaderboard.
// In production this is replaced by a backend route calling Claude with the full
// week-over-week diff; this client-side composition keeps the demo offline-safe.
export function AIDigest() {
  const { data: kpis } = useQuery({ queryKey: ["digest-kpis"], queryFn: () => api.analytics.kpis("30d") });
  const { data: hotspots } = useQuery({ queryKey: ["digest-hot"], queryFn: () => api.analytics.hotspots("30d", 3) });
  const { data: builders } = useQuery({ queryKey: ["digest-blds"], queryFn: () => api.builders.leaderboard("30d", 3) });

  const isLoading = !kpis || !hotspots || !builders;

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-muted-foreground">
        <Sparkles className="h-3 w-3 text-primary" />
        AI Narrative · last 30 days
      </div>
      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
        </div>
      ) : (
        <div className="space-y-2 text-xs leading-relaxed">
          <p>
            <span className="num font-semibold text-foreground">{kpis.permits_this_period.toLocaleString()}</span>{" "}
            permits issued in the last 30 days,{" "}
            <span className={kpis.velocity_pct >= 0 ? "text-primary" : "text-destructive"}>
              {kpis.velocity_pct >= 0 ? "up" : "down"} {Math.abs(kpis.velocity_pct).toFixed(1)}%
            </span>{" "}
            from the prior period.
          </p>
          {hotspots && hotspots.length > 0 && (
            <p>
              <span className="font-semibold text-foreground">Hottest submarkets:</span>{" "}
              {hotspots.map((h, i) => (
                <span key={h.zip_code}>
                  <span className="num">{h.zip_code}</span> ({h.permit_count} permits
                  {h.velocity_pct !== 0 && (
                    <span className={h.velocity_pct > 0 ? "text-primary" : "text-destructive"}>
                      , {h.velocity_pct > 0 ? "+" : ""}{h.velocity_pct.toFixed(0)}%
                    </span>
                  )}
                  ){i < hotspots.length - 1 ? ", " : "."}
                </span>
              ))}
            </p>
          )}
          {builders && builders.length > 0 && (
            <p>
              <span className="font-semibold text-foreground">Top movers:</span>{" "}
              {builders.map((b, i) => (
                <span key={b.builder}>
                  {b.builder} ({b.permit_count}){i < builders.length - 1 ? ", " : "."}
                </span>
              ))}
            </p>
          )}
          <p className="text-muted-foreground">
            Tip: open the Opportunity Finder to surface small-builder gaps or accelerating ZIPs.
          </p>
        </div>
      )}
    </div>
  );
}
