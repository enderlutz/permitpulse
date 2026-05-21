import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useClassColor } from "@/lib/colors";
import { formatRelativeDate } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";

export function RecentPermits() {
  const { data, isLoading } = useQuery({
    queryKey: ["recent-permits"],
    queryFn: () => api.permits.recent(30, 50),
  });

  if (isLoading) {
    return (
      <div className="space-y-1">
        {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="space-y-0.5 pr-1">
        {data?.map((p) => (
          <div
            key={p.id}
            className="flex items-start gap-2 rounded border-l-2 px-2 py-1.5 text-xs hover:bg-secondary/40"
            style={{ borderLeftColor: useClassColor(p.use_class) }}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="num text-[10px] font-medium text-muted-foreground">{p.zip_code}</span>
                <span className="truncate text-[11px]">{p.address || "—"}</span>
              </div>
              <div className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground">
                <span>{p.permit_type}</span>
                {p.use_class && <span>· {p.use_class}</span>}
                {p.builder && <span>· {p.builder}</span>}
              </div>
            </div>
            <span className="num shrink-0 text-[10px] text-muted-foreground">
              {formatRelativeDate(p.permit_date)}
            </span>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
}
