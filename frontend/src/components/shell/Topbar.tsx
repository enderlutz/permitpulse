import { useState } from "react";
import { Search, Bell, Filter, RotateCcw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useWorkspace } from "@/store/workspace";

export function Topbar() {
  const filters = useWorkspace((s) => s.filters);
  const setFilter = useWorkspace((s) => s.setFilter);
  const clearFilters = useWorkspace((s) => s.clearFilters);
  const [search, setSearch] = useState("");

  const activeCount = [filters.zip, filters.builder, filters.permitType, filters.useClass].filter(Boolean).length;

  const applySearch = () => {
    const v = search.trim();
    if (!v) return;
    // 5-digit ZIP → ZIP filter; anything else → builder match
    if (/^\d{5}$/.test(v)) {
      setFilter("zip", v);
    } else {
      setFilter("builder", v);
    }
    setSearch("");
  };

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border bg-surface/80 px-4 backdrop-blur">
      <div className="flex items-center gap-1.5">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
        </span>
        <span className="text-xs text-muted-foreground">Live · 2025 archive</span>
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

      {/* Active filter chips */}
      <div className="flex items-center gap-1.5">
        {filters.zip && (
          <FilterChip label="ZIP" value={filters.zip} onClear={() => setFilter("zip", null)} />
        )}
        {filters.builder && (
          <FilterChip label="Builder" value={filters.builder} onClear={() => setFilter("builder", null)} />
        )}
      </div>

      <div className="flex items-center gap-2">
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
          </SelectContent>
        </Select>

        <Select
          value={filters.permitType ?? "__all__"}
          onValueChange={(v) => setFilter("permitType", v === "__all__" ? null : v)}
        >
          <SelectTrigger className="w-36">
            <SelectValue placeholder="All permits" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All permits</SelectItem>
            <SelectItem value="Building Pmt">Building</SelectItem>
            <SelectItem value="OCC-BLDG PMT">Cert. of Occupancy</SelectItem>
            <SelectItem value="Demolition">Demolition</SelectItem>
            <SelectItem value="MDI Structure">MDI Structural</SelectItem>
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
