import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { builderColor } from "@/lib/colors";
import { useWorkspace } from "@/store/workspace";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function BuilderLeaderboard() {
  const period = useWorkspace((s) => s.filters.period);
  const builderFilter = useWorkspace((s) => s.filters.builder);
  const setFilter = useWorkspace((s) => s.setFilter);
  const { data, isLoading } = useQuery({
    queryKey: ["builders-leaderboard", period],
    queryFn: () => api.builders.leaderboard(period, 10),
  });
  const max = data?.[0]?.permit_count ?? 1;

  return (
    <div className="flex h-full flex-col gap-1">
      {isLoading
        ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-7 w-full" />)
        : data?.map((row) => {
            const pct = (row.permit_count / max) * 100;
            const active = builderFilter === row.builder;
            return (
              <button
                key={row.builder}
                onClick={() => setFilter("builder", active ? null : row.builder)}
                className={cn(
                  "group relative flex items-center justify-between rounded px-2 py-1 text-left text-xs transition-colors hover:bg-secondary/60",
                  active && "bg-secondary"
                )}
              >
                <div
                  className="absolute inset-y-0 left-0 rounded bg-gradient-to-r opacity-15"
                  style={{
                    width: `${pct}%`,
                    backgroundImage: `linear-gradient(to right, ${builderColor(row.builder)}, transparent)`,
                  }}
                />
                <div className="relative flex items-center gap-1.5">
                  <div className="h-2 w-2 rounded-full" style={{ background: builderColor(row.builder) }} />
                  <span className="truncate">{row.builder}</span>
                </div>
                <span className="num relative text-muted-foreground">{row.permit_count}</span>
              </button>
            );
          })}
      {data && data.length === 0 && (
        <div className="flex flex-1 items-center justify-center text-xs text-muted-foreground">
          No builder data in period
        </div>
      )}
    </div>
  );
}
