import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { api } from "@/lib/api";
import { useWorkspace } from "@/store/workspace";
import { Skeleton } from "@/components/ui/skeleton";

export function VolumeTrend() {
  const period = useWorkspace((s) => s.filters.period);
  const zip = useWorkspace((s) => s.filters.zip);
  const { data, isLoading } = useQuery({
    queryKey: ["volume-trend", period, zip],
    queryFn: () => api.analytics.timeseries({ period, bucket: "week", zip }),
  });

  if (isLoading) return <Skeleton className="h-full w-full" />;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -10 }}>
        <defs>
          <linearGradient id="volumeFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.4} />
            <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="2 4" stroke="hsl(var(--border))" vertical={false} />
        <XAxis dataKey="bucket" tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 9 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
        <YAxis tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 9 }} axisLine={false} tickLine={false} width={32} />
        <Tooltip
          contentStyle={{ background: "hsl(220 18% 9%)", border: "1px solid hsl(220 14% 18%)", fontSize: 11 }}
          labelStyle={{ color: "hsl(var(--muted-foreground))", fontSize: 10 }}
        />
        <Area type="monotone" dataKey="count" stroke="hsl(var(--primary))" strokeWidth={1.5} fill="url(#volumeFill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
