import { Search, Bell, Filter, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useWorkspace } from "@/store/workspace";

export function Topbar() {
  const filters = useWorkspace((s) => s.filters);
  const setFilter = useWorkspace((s) => s.setFilter);
  const clearFilters = useWorkspace((s) => s.clearFilters);

  const activeCount = [filters.zip, filters.builder, filters.permitType, filters.useClass].filter(Boolean).length;

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
          placeholder="Search permits, addresses, builders, ZIPs… (⌘K)"
          className="h-8 w-full max-w-md rounded-md border border-border bg-surface pl-8 pr-3 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />
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
          <Button variant="ghost" size="sm" onClick={clearFilters} className="gap-1.5">
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
