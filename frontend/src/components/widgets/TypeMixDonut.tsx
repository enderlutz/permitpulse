import { useQuery } from "@tanstack/react-query";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { api } from "@/lib/api";
import { useWorkspace } from "@/store/workspace";
import { Skeleton } from "@/components/ui/skeleton";

const COLORS = ["#10b981", "#06b6d4", "#a855f7", "#f59e0b", "#ec4899", "#3b82f6", "#84cc16", "#f97316", "#64748b"];

export function TypeMixDonut() {
  const period = useWorkspace((s) => s.filters.period);
  const { data, isLoading } = useQuery({
    queryKey: ["type-mix", period],
    queryFn: () => api.analytics.typeMix(period),
  });

  if (isLoading) return <Skeleton className="h-full w-full" />;
  if (!data?.length) return <div className="flex h-full items-center justify-center text-xs text-muted-foreground">No data</div>;

  const total = data.reduce((s, r) => s + r.count, 0);

  return (
    <div className="flex h-full items-center gap-2">
      <div className="h-full max-h-40 w-1/2">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="count" nameKey="type" innerRadius="55%" outerRadius="90%" paddingAngle={2}>
              {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip
              contentStyle={{ background: "hsl(220 18% 9%)", border: "1px solid hsl(220 14% 18%)", fontSize: 11 }}
              formatter={(v: any) => [`${v}`, ""]}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="flex-1 space-y-1 text-xs">
        {data.map((row, i) => (
          <div key={row.type} className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-1.5">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
              <span className="truncate">{row.type}</span>
            </div>
            <span className="num shrink-0 text-muted-foreground">
              {row.count} <span className="text-[10px]">· {((row.count / total) * 100).toFixed(0)}%</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
