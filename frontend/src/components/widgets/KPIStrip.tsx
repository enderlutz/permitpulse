import { useQuery } from "@tanstack/react-query";
import { TrendingUp, TrendingDown, Building2, Flame, MapPin } from "lucide-react";
import { api } from "@/lib/api";
import { useWorkspace } from "@/store/workspace";
import { formatNum, formatPct, cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

export function KPIStrip() {
  const period = useWorkspace((s) => s.filters.period);
  const { data, isLoading } = useQuery({
    queryKey: ["kpis", period],
    queryFn: () => api.analytics.kpis(period),
  });

  const items = [
    {
      label: "Permits this period",
      value: data?.permits_this_period ?? null,
      sub: data ? formatPct(data.velocity_pct) : "—",
      subPositive: (data?.velocity_pct ?? 0) >= 0,
      icon: Building2,
    },
    {
      label: "vs Prior period",
      value: data?.permits_prev_period ?? null,
      sub: data ? `${formatNum(Math.abs((data.permits_this_period ?? 0) - (data.permits_prev_period ?? 0)))} ${(data.permits_this_period ?? 0) >= (data.permits_prev_period ?? 0) ? "more" : "less"}` : "—",
      subPositive: (data?.velocity_pct ?? 0) >= 0,
      icon: TrendingUp,
    },
    {
      label: "Active hotspots",
      value: data?.hotspot_count ?? null,
      sub: "ZIPs ≥ 25 permits",
      subPositive: true,
      icon: Flame,
    },
    {
      label: "Top ZIP",
      value: data?.top_zip ?? "—",
      sub: data?.top_zip_count ? `${formatNum(data.top_zip_count)} permits` : "—",
      subPositive: true,
      icon: MapPin,
      isText: true,
    },
    {
      label: "Top builder",
      value: data?.top_builder ?? "—",
      sub: data?.top_builder_count ? `${formatNum(data.top_builder_count)} permits` : "—",
      subPositive: true,
      icon: Building2,
      isText: true,
    },
  ];

  return (
    <div className="grid h-full grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-5">
      {items.map((item, i) => (
        <div key={i} className="flex flex-col justify-between rounded-md border border-border bg-surface/60 p-2.5">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-[10px] uppercase tracking-wider text-muted-foreground">{item.label}</span>
            <item.icon className="h-3 w-3 text-muted-foreground/60" />
          </div>
          {isLoading ? (
            <Skeleton className="mt-1 h-7 w-20" />
          ) : (
            <div
              className={cn(
                "mt-1 truncate font-semibold leading-tight",
                item.isText ? "num text-lg" : "num text-2xl"
              )}
            >
              {typeof item.value === "number" ? formatNum(item.value) : item.value}
            </div>
          )}
          <div
            className={cn(
              "mt-1 flex items-center gap-1 text-[11px]",
              item.subPositive ? "text-primary" : "text-destructive"
            )}
          >
            {item.subPositive ? <TrendingUp className="h-2.5 w-2.5" /> : <TrendingDown className="h-2.5 w-2.5" />}
            <span className="truncate">{item.sub}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
