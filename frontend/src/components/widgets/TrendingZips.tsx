import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useWorkspace } from "@/store/workspace";
import { formatPct, cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

function Sparkline({ data, color = "hsl(var(--primary))" }: { data: number[]; color?: string }) {
  if (data.length < 2) return null;
  const max = Math.max(...data, 1);
  const w = 80;
  const h = 18;
  const pts = data.map((v, i) => `${(i * w) / (data.length - 1)},${h - (v / max) * h}`).join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      <polyline fill="none" stroke={color} strokeWidth="1.2" points={pts} />
      <circle cx={w} cy={h - (data[data.length - 1] / max) * h} r="1.6" fill={color} />
    </svg>
  );
}

export function TrendingZips() {
  const period = useWorkspace((s) => s.filters.period);
  const zipFilter = useWorkspace((s) => s.filters.zip);
  const setFilter = useWorkspace((s) => s.setFilter);
  const { data, isLoading } = useQuery({
    queryKey: ["hotspots", period],
    queryFn: () => api.analytics.hotspots(period, 10),
  });

  return (
    <div className="flex h-full flex-col gap-0.5">
      {isLoading
        ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-7 w-full" />)
        : data?.map((row) => {
            const active = zipFilter === row.zip_code;
            return (
              <button
                key={row.zip_code}
                onClick={() => setFilter("zip", active ? null : row.zip_code)}
                className={cn(
                  "flex items-center justify-between gap-2 rounded px-2 py-1 text-left text-xs transition-colors hover:bg-secondary/60",
                  active && "bg-secondary"
                )}
              >
                <span className="num shrink-0 font-medium">{row.zip_code}</span>
                <span className="num shrink-0 text-muted-foreground">{row.permit_count}</span>
                <Sparkline data={row.sparkline} />
                <span
                  className={cn(
                    "num shrink-0 text-[10px]",
                    row.velocity_pct >= 0 ? "text-primary" : "text-destructive"
                  )}
                >
                  {formatPct(row.velocity_pct, 0)}
                </span>
              </button>
            );
          })}
    </div>
  );
}
