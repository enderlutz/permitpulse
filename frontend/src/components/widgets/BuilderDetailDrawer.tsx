import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { builderColor } from "@/lib/colors";
import { useWorkspace } from "@/store/workspace";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { X, MapPin, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface BuilderDetailDrawerProps {
  builder: string | null;
  onClose: () => void;
}

interface Footprint {
  builder: string;
  permit_count: number;
  total_value: number;
  valued_count: number;
  zip_codes: [string, number][];
  permit_types: [string, number][];
  use_classes: [string, number][];
  monthly_trend: { month: string; count: number }[];
  recent_permits: {
    id: number;
    permit_date: string | null;
    address: string | null;
    zip_code: string | null;
    permit_type: string | null;
    project_value: number | null;
  }[];
}

function fmtMoney(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}k`;
  return `$${n.toFixed(0)}`;
}

export function BuilderDetailDrawer({ builder, onClose }: BuilderDetailDrawerProps) {
  const period = useWorkspace((s) => s.filters.period);
  const setFilter = useWorkspace((s) => s.setFilter);

  const { data, isLoading, error } = useQuery<Footprint>({
    queryKey: ["builder-footprint", builder, period],
    queryFn: () => api.builders.footprint(builder!, period),
    enabled: !!builder,
  });

  if (!builder) return null;

  const color = builderColor(builder);
  const maxMonth = data?.monthly_trend.reduce((m, x) => (x.count > m ? x.count : m), 1) ?? 1;
  const maxZip = data?.zip_codes[0]?.[1] ?? 1;
  const maxType = data?.permit_types[0]?.[1] ?? 1;

  return (
    <div
      className="fixed right-0 top-0 z-[500] flex h-full w-[420px] max-w-[95vw] flex-col border-l border-border bg-background shadow-2xl"
      role="dialog"
      aria-label={`${builder} detail`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b border-border px-4 py-3">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <span
            className="h-3 w-3 shrink-0 rounded-full"
            style={{ background: color }}
            aria-hidden
          />
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">{builder}</div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Builder profile · {period}
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {isLoading && (
          <div className="space-y-3">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        )}

        {error && (
          <div className="rounded-md border border-border bg-secondary/40 px-3 py-4 text-center text-xs text-muted-foreground">
            No permit activity for this builder in the selected period.
          </div>
        )}

        {data && (
          <>
            {/* Summary stats */}
            <div className="grid grid-cols-3 gap-2">
              <Stat label="Permits" value={data.permit_count.toLocaleString()} />
              <Stat
                label="Reported value"
                value={data.total_value > 0 ? fmtMoney(data.total_value) : "—"}
                sub={data.valued_count > 0 ? `${data.valued_count} w/ value` : undefined}
              />
              <Stat
                label="Active ZIPs"
                value={data.zip_codes.length.toString()}
              />
            </div>

            {/* Filter + isolate buttons */}
            <div className="mt-3 flex gap-2">
              <Button
                size="sm"
                variant="secondary"
                className="h-7 flex-1 text-[11px]"
                onClick={() => {
                  setFilter("builder", builder);
                  onClose();
                }}
              >
                Filter dashboard to {builder.split(" ")[0]}
              </Button>
            </div>

            {/* Monthly trend */}
            {data.monthly_trend.length > 0 && (
              <Section title="Monthly volume">
                <div className="flex items-end gap-0.5 h-16">
                  {data.monthly_trend.slice(-12).map((m) => (
                    <div
                      key={m.month}
                      className="flex flex-1 flex-col items-center gap-0.5"
                      title={`${m.month}: ${m.count} permits`}
                    >
                      <div
                        className="w-full rounded-sm"
                        style={{
                          height: `${Math.max(2, (m.count / maxMonth) * 56)}px`,
                          background: color,
                          opacity: 0.75,
                        }}
                      />
                    </div>
                  ))}
                </div>
                <div className="mt-1 flex justify-between text-[9px] text-muted-foreground">
                  <span>{data.monthly_trend.slice(-12)[0]?.month ?? "—"}</span>
                  <span>{data.monthly_trend.slice(-1)[0]?.month ?? "—"}</span>
                </div>
              </Section>
            )}

            {/* Top ZIPs */}
            {data.zip_codes.length > 0 && (
              <Section title="Top ZIP codes">
                <div className="flex flex-col gap-1">
                  {data.zip_codes.slice(0, 8).map(([zip, n]) => (
                    <button
                      key={zip}
                      onClick={() => {
                        setFilter("zip", zip);
                      }}
                      className="group relative flex items-center justify-between rounded px-2 py-1 text-[11px] hover:bg-secondary/60"
                    >
                      <div
                        className="absolute inset-y-0 left-0 rounded bg-secondary"
                        style={{ width: `${(n / maxZip) * 100}%`, opacity: 0.4 }}
                      />
                      <span className="num relative font-medium">{zip}</span>
                      <span className="num relative text-muted-foreground">{n}</span>
                    </button>
                  ))}
                </div>
              </Section>
            )}

            {/* Permit type mix */}
            {data.permit_types.length > 0 && (
              <Section title="Permit type mix">
                <div className="flex flex-col gap-1">
                  {data.permit_types.slice(0, 6).map(([t, n]) => (
                    <div
                      key={t}
                      className="relative flex items-center justify-between rounded px-2 py-1 text-[11px]"
                    >
                      <div
                        className="absolute inset-y-0 left-0 rounded"
                        style={{
                          width: `${(n / maxType) * 100}%`,
                          background: color,
                          opacity: 0.18,
                        }}
                      />
                      <span className="relative truncate">{t}</span>
                      <span className="num relative text-muted-foreground">{n}</span>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Recent permits */}
            {data.recent_permits.length > 0 && (
              <Section title="Recent permits">
                <div className="flex flex-col">
                  {data.recent_permits.slice(0, 10).map((p) => (
                    <div
                      key={p.id}
                      className={cn(
                        "flex items-start gap-2 border-b border-border/40 py-1.5 text-[11px] last:border-b-0"
                      )}
                    >
                      <MapPin className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground" />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="num text-foreground">{p.permit_date ?? "—"}</span>
                          <span className="num text-[10px] text-muted-foreground">
                            {p.project_value && p.project_value > 0
                              ? fmtMoney(p.project_value)
                              : ""}
                          </span>
                        </div>
                        <div className="truncate text-foreground/85">
                          {p.address || "—"} {p.zip_code ? `· ${p.zip_code}` : ""}
                        </div>
                        {p.permit_type && (
                          <div className="text-[10px] text-muted-foreground">
                            {p.permit_type}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </Section>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-md border border-border bg-secondary/40 px-2 py-2">
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="num text-sm font-semibold">{value}</div>
      {sub && <div className="text-[9px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-4">
      <div className="mb-1.5 flex items-center gap-1 text-[9px] font-medium uppercase tracking-wider text-muted-foreground">
        {title}
        <ChevronRight className="h-2.5 w-2.5 opacity-50" />
      </div>
      {children}
    </div>
  );
}
