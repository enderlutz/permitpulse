import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Database, Clock } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useClassColor } from "@/lib/colors";

const SOURCE_ORDER = ["City of Houston", "Harris County"];

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

function fmtDate(iso: string): string {
  // iso is YYYY-MM-DD
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

export function DailyReportPage() {
  const [days, setDays] = useState(14);
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["ingest-report", days],
    queryFn: () => api.permits.ingestReport(days),
  });

  const sources = data
    ? Array.from(new Set([...SOURCE_ORDER, ...Object.keys(data.totals)])).filter((s) => data.totals[s] != null || SOURCE_ORDER.includes(s))
    : SOURCE_ORDER;

  return (
    <div className="flex h-full flex-col overflow-auto p-4">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Daily Report</h1>
          <p className="text-xs text-muted-foreground">
            New permits pulled from each source · last{" "}
            <span className="text-foreground">{days} days</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
            <Clock className="h-3 w-3" /> Last pull {timeAgo(data?.latest_ingest ?? null)}
          </div>
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={cn(
                "rounded px-2 py-1 text-[11px] transition-colors",
                days === d ? "bg-secondary text-foreground" : "text-muted-foreground hover:bg-secondary/60"
              )}
            >
              {d}d
            </button>
          ))}
          <button
            onClick={() => refetch()}
            className="rounded p-1.5 text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
            title="Refresh"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">Loading…</div>
      ) : !data ? (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">No data</div>
      ) : (
        <>
          {/* Source totals */}
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {sources.map((s) => (
              <div key={s} className="rounded-lg border border-border bg-surface p-3">
                <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                  <Database className="h-3 w-3" /> {s}
                </div>
                <div className="num mt-1 text-2xl font-semibold">{(data.totals[s] ?? 0).toLocaleString()}</div>
                <div className="text-[10px] text-muted-foreground">permits pulled · {days}d</div>
              </div>
            ))}
          </div>

          {/* Per-day breakdown */}
          <div className="mb-4 rounded-lg border border-border bg-surface">
            <div className="border-b border-border px-3 py-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
              By day
            </div>
            <div className="divide-y divide-border/60">
              {data.days.length === 0 && (
                <div className="px-3 py-6 text-center text-xs text-muted-foreground">No new permits in this window.</div>
              )}
              {data.days.map((d) => (
                <div key={d.date} className="flex items-center justify-between px-3 py-2 text-xs">
                  <span className="w-28 text-muted-foreground">{fmtDate(d.date)}</span>
                  <div className="flex flex-1 items-center gap-3">
                    {sources.map((s) =>
                      d.sources[s] ? (
                        <span key={s} className="text-[11px] text-muted-foreground">
                          {s.replace("City of ", "")}: <span className="num text-foreground">{d.sources[s].toLocaleString()}</span>
                        </span>
                      ) : null
                    )}
                  </div>
                  <span className="num font-medium">{d.total.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Latest permits */}
          <div className="rounded-lg border border-border bg-surface">
            <div className="border-b border-border px-3 py-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
              Latest pulls
            </div>
            <div className="divide-y divide-border/60">
              {data.recent.map((p) => (
                <div key={p.id} className="flex items-center gap-2 px-3 py-1.5 text-[11px]">
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ background: useClassColor(p.use_class) }}
                    title={p.use_class || "unknown"}
                  />
                  <span className="w-28 shrink-0 truncate text-muted-foreground" title={p.source || ""}>{p.source}</span>
                  <span className="flex-1 truncate" title={p.address || ""}>{p.address || "—"}</span>
                  <span className="hidden w-40 shrink-0 truncate text-muted-foreground md:block" title={p.builder || ""}>
                    {p.builder || ""}
                  </span>
                  <span className="hidden w-24 shrink-0 truncate text-muted-foreground sm:block">{p.permit_type || ""}</span>
                  <span className="w-16 shrink-0 text-right text-muted-foreground">{timeAgo(p.ingested_at)}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
