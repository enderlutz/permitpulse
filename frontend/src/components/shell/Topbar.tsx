import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Bell, Filter, RotateCcw, X, Calendar, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { useWorkspace } from "@/store/workspace";
import { api, API_BASE } from "@/lib/api";
import { cn, formatNum } from "@/lib/utils";

export function Topbar() {
  const filters = useWorkspace((s) => s.filters);
  const setFilter = useWorkspace((s) => s.setFilter);
  const clearFilters = useWorkspace((s) => s.clearFilters);
  const [search, setSearch] = useState("");

  const { data: years } = useQuery({
    queryKey: ["permit-years"],
    queryFn: () => api.permits.years(),
    staleTime: 5 * 60_000,
  });

  const { data: meta } = useQuery({
    queryKey: ["permit-meta"],
    queryFn: () => api.permits.meta(),
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });

  const lastUpdatedLabel = (() => {
    if (!meta?.latest_ingest) return null;
    const dt = new Date(meta.latest_ingest);
    const now = new Date();
    const diffMs = now.getTime() - dt.getTime();
    const mins = Math.floor(diffMs / 60_000);
    if (mins < 1) return "Updated just now";
    if (mins < 60) return `Updated ${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `Updated ${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days === 1) return "Updated yesterday";
    return `Updated ${days}d ago`;
  })();

  const lastUpdatedFull = meta?.latest_ingest
    ? new Date(meta.latest_ingest).toLocaleString()
    : "";

  const activeYears = filters.years;
  const yearsActive = activeYears != null && activeYears.length > 0;
  const activeCount =
    [filters.zip, filters.builder, filters.permitType, filters.nature, filters.useClass].filter(Boolean).length +
    (yearsActive ? 1 : 0);

  const applySearch = () => {
    const v = search.trim();
    if (!v) return;
    if (/^\d{5}$/.test(v)) {
      setFilter("zip", v);
    } else {
      setFilter("builder", v);
    }
    setSearch("");
  };

  const toggleYear = (yr: number) => {
    const current = activeYears ?? [];
    const next = current.includes(yr) ? current.filter((y) => y !== yr) : [...current, yr];
    // Empty selection = treat as "all years" (null) so UX matches intuition
    setFilter("years", next.length === 0 ? null : next);
  };

  const yearButtonLabel = (() => {
    if (!yearsActive) return "All years";
    if (activeYears!.length === 1) return String(activeYears![0]);
    if (activeYears!.length === 2) return activeYears!.join(" + ");
    return `${activeYears!.length} years`;
  })();

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border bg-surface/80 px-4 backdrop-blur">
      <div className="flex items-center gap-1.5" title={lastUpdatedFull || `API: ${API_BASE}`}>
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
        </span>
        <span className="text-xs font-medium text-foreground/90">Live</span>
        {lastUpdatedLabel && (
          <span className="text-xs text-muted-foreground">· {lastUpdatedLabel}</span>
        )}
        {meta && (
          <span className="text-[10px] text-muted-foreground/70">
            · {formatNum(meta.total)} permits · {formatNum(meta.geocoded)} mapped
          </span>
        )}
      </div>

      <div className="relative flex flex-1 items-center">
        <Search className="absolute left-2.5 h-3.5 w-3.5 text-muted-foreground" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && applySearch()}
          placeholder="Search ZIP (e.g. 77079) or builder name… ↵"
          className="h-8 w-full max-w-md rounded-md border border-border bg-surface pl-8 pr-3 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>

      <div className="flex items-center gap-1.5">
        {filters.zip && (
          <FilterChip label="ZIP" value={filters.zip} onClear={() => setFilter("zip", null)} />
        )}
        {filters.builder && (
          <FilterChip label="Builder" value={filters.builder} onClear={() => setFilter("builder", null)} />
        )}
      </div>

      <div className="flex items-center gap-2">
        {/* Year multi-select */}
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className={cn(
                "h-7 gap-1.5 px-2",
                yearsActive && "border-primary/40 bg-primary/10 text-primary"
              )}
            >
              <Calendar className="h-3 w-3" />
              <span className="text-xs">{yearButtonLabel}</span>
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-56 p-1.5">
            <div className="mb-1 px-1 text-[10px] uppercase tracking-widest text-muted-foreground">
              Years in data
            </div>
            <div className="space-y-0.5">
              {years && years.length === 0 && (
                <div className="px-2 py-1 text-xs text-muted-foreground">No data</div>
              )}
              {years?.slice().reverse().map((y) => {
                const isActive = activeYears?.includes(y.year) ?? false;
                return (
                  <button
                    key={y.year}
                    onClick={() => toggleYear(y.year)}
                    className={cn(
                      "flex w-full items-center justify-between rounded px-2 py-1 text-xs transition-colors hover:bg-secondary/60",
                      isActive && "bg-secondary"
                    )}
                  >
                    <div className="flex items-center gap-1.5">
                      <div
                        className={cn(
                          "flex h-3 w-3 items-center justify-center rounded border",
                          isActive ? "border-primary bg-primary text-primary-foreground" : "border-border"
                        )}
                      >
                        {isActive && <Check className="h-2.5 w-2.5" />}
                      </div>
                      <span className="num font-medium">{y.year}</span>
                    </div>
                    <span className="num text-[10px] text-muted-foreground">{formatNum(y.count)}</span>
                  </button>
                );
              })}
            </div>
            {yearsActive && (
              <div className="mt-1 border-t border-border pt-1">
                <button
                  onClick={() => setFilter("years", null)}
                  className="w-full rounded px-2 py-1 text-left text-[10px] text-muted-foreground hover:bg-secondary"
                >
                  Clear → show all years
                </button>
              </div>
            )}
          </PopoverContent>
        </Popover>

        <Select
          value={filters.useClass ?? "__all__"}
          onValueChange={(v) => setFilter("useClass", v === "__all__" ? null : v)}
        >
          <SelectTrigger className="w-32">
            <SelectValue placeholder="All uses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All uses</SelectItem>
            <SelectItem value="warehouse">Warehouse</SelectItem>
            <SelectItem value="retail">Retail</SelectItem>
            <SelectItem value="office">Office</SelectItem>
            <SelectItem value="restaurant">Restaurant</SelectItem>
            <SelectItem value="apartment">Apartment</SelectItem>
            <SelectItem value="residential">Residential</SelectItem>
            <SelectItem value="clinic">Medical / Clinic</SelectItem>
            <SelectItem value="school">School</SelectItem>
            <SelectItem value="church">Church</SelectItem>
            <SelectItem value="hotel">Hotel</SelectItem>
            <SelectItem value="general">Unknown / Pending / General</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={filters.nature ?? "__all__"}
          onValueChange={(v) => setFilter("nature", v === "__all__" ? null : v)}
        >
          <SelectTrigger className="w-36">
            <SelectValue placeholder="All permits" />
          </SelectTrigger>
          <SelectContent>
            {/* Cross-source: matches both City-of-Houston and Harris County
                permit vocabularies via the permit_nature field. */}
            <SelectItem value="__all__">All permits</SelectItem>
            <SelectItem value="building">Building (all)</SelectItem>
            <SelectItem value="new_building">New construction</SelectItem>
            <SelectItem value="remodel">Remodel / Tenant</SelectItem>
            <SelectItem value="fire">Fire</SelectItem>
            <SelectItem value="site_civil">Site / Civil</SelectItem>
            <SelectItem value="sign">Sign</SelectItem>
          </SelectContent>
        </Select>

        <Select value={filters.period} onValueChange={(v) => setFilter("period", v as any)}>
          <SelectTrigger className="w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7d">Last 7 days</SelectItem>
            <SelectItem value="30d">Last 30 days</SelectItem>
            <SelectItem value="90d">Last 90 days</SelectItem>
            <SelectItem value="12mo">Last 12 months</SelectItem>
          </SelectContent>
        </Select>

        {activeCount > 0 && (
          <Button variant="ghost" size="sm" onClick={clearFilters} className="gap-1.5" title="Clear all filters">
            <Filter className="h-3 w-3" />
            <Badge variant="success">{activeCount}</Badge>
            <RotateCcw className="h-3 w-3 opacity-50" />
          </Button>
        )}

        <Button variant="ghost" size="icon" aria-label="Notifications">
          <Bell className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}

function FilterChip({ label, value, onClear }: { label: string; value: string; onClear: () => void }) {
  return (
    <button
      onClick={onClear}
      className="group flex items-center gap-1 rounded-full border border-border bg-secondary px-2 py-0.5 text-[10px] hover:bg-destructive/20 hover:border-destructive/40"
      title={`Clear ${label}: ${value}`}
    >
      <span className="text-muted-foreground">{label}:</span>
      <span className="num font-medium">{value}</span>
      <X className="h-2.5 w-2.5 opacity-50 group-hover:opacity-100" />
    </button>
  );
}
