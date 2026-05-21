import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useWorkspace } from "@/store/workspace";
import { useClassColor } from "@/lib/colors";
import { formatDate, cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";

export function PermitsPage() {
  const filters = useWorkspace((s) => s.filters);
  const setFilter = useWorkspace((s) => s.setFilter);
  const [page, setPage] = useState(0);
  const limit = 100;

  const { data, isLoading } = useQuery({
    queryKey: ["permits-table", filters, page],
    queryFn: () =>
      api.permits.list({
        period: filters.period,
        zip: filters.zip,
        builder: filters.builder,
        permit_type: filters.permitType,
        use_class: filters.useClass,
        limit,
        offset: page * limit,
      }),
  });

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border bg-surface/40 px-4 py-2">
        <div>
          <h1 className="text-base font-semibold tracking-tight">Permits</h1>
          <p className="text-xs text-muted-foreground">Full filterable table view · {data?.length ?? 0} rows on this page</p>
        </div>
      </div>
      <ScrollArea className="flex-1">
        <table className="w-full text-xs">
          <thead className="sticky top-0 z-10 bg-surface text-[10px] uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left">Date</th>
              <th className="px-3 py-2 text-left">Project No</th>
              <th className="px-3 py-2 text-left">Type</th>
              <th className="px-3 py-2 text-left">Use</th>
              <th className="px-3 py-2 text-left">ZIP</th>
              <th className="px-3 py-2 text-left">Address</th>
              <th className="px-3 py-2 text-left">Builder</th>
              <th className="px-3 py-2 text-right">Sq Ft</th>
            </tr>
          </thead>
          <tbody>
            {isLoading &&
              Array.from({ length: 12 }).map((_, i) => (
                <tr key={i}>
                  <td colSpan={8} className="px-3 py-1">
                    <Skeleton className="h-5 w-full" />
                  </td>
                </tr>
              ))}
            {data?.map((p, i) => (
              <tr
                key={p.id}
                className={cn(
                  "border-b border-border/60 transition-colors hover:bg-secondary/30",
                  i % 2 ? "bg-surface/30" : ""
                )}
              >
                <td className="num px-3 py-1.5 text-muted-foreground">{formatDate(p.permit_date)}</td>
                <td className="num px-3 py-1.5">{p.project_no}</td>
                <td className="px-3 py-1.5">{p.permit_type}</td>
                <td className="px-3 py-1.5">
                  {p.use_class && (
                    <span
                      className="rounded-full px-1.5 py-0.5 text-[10px]"
                      style={{ background: `${useClassColor(p.use_class)}20`, color: useClassColor(p.use_class) }}
                    >
                      {p.use_class}
                    </span>
                  )}
                </td>
                <td className="px-3 py-1.5">
                  <button
                    onClick={() => setFilter("zip", p.zip_code)}
                    className="num text-primary hover:underline"
                  >
                    {p.zip_code}
                  </button>
                </td>
                <td className="px-3 py-1.5 max-w-xs truncate">{p.address}</td>
                <td className="px-3 py-1.5">
                  {p.builder ? (
                    <button onClick={() => setFilter("builder", p.builder!)} className="hover:underline">
                      {p.builder}
                    </button>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
                <td className="num px-3 py-1.5 text-right text-muted-foreground">
                  {p.square_feet?.toLocaleString() || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollArea>
      <div className="flex shrink-0 items-center justify-between border-t border-border px-4 py-2 text-xs">
        <span className="text-muted-foreground">Page {page + 1}</span>
        <div className="flex gap-1">
          <button
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
            className="rounded border border-border px-2 py-0.5 disabled:opacity-40"
          >
            ← Prev
          </button>
          <button
            disabled={(data?.length ?? 0) < limit}
            onClick={() => setPage(page + 1)}
            className="rounded border border-border px-2 py-0.5 disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
