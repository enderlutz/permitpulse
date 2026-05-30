import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import L from "leaflet";
import "leaflet.heat";
import { api } from "@/lib/api";
import { useWorkspace } from "@/store/workspace";
import { recencyColor, builderColor, useClassColor } from "@/lib/colors";
import { Button } from "@/components/ui/button";
import { Layers, Flame, MapPin, Building2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Permit } from "@/lib/types";
import { MapLegend } from "./MapLegend";
import { BuilderDetailDrawer } from "./BuilderDetailDrawer";

const HOUSTON_CENTER: L.LatLngExpression = [29.7604, -95.3698];

type ColorMode = "recency" | "builder" | "useClass";

export function MapWidget() {
  const mapEl = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const heatRef = useRef<any>(null);
  const [colorMode, setColorMode] = useState<ColorMode>("recency");
  const [showHeat, setShowHeat] = useState(true);
  const [showPins, setShowPins] = useState(true);
  const [selectedPermit, setSelectedPermit] = useState<Permit | null>(null);
  const [detailBuilder, setDetailBuilder] = useState<string | null>(null);

  const filters = useWorkspace((s) => s.filters);
  const setFilter = useWorkspace((s) => s.setFilter);

  const { data: permits } = useQuery({
    queryKey: ["permits-map", filters.period, filters.zip, filters.builder, filters.permitType, filters.useClass, filters.years, filters.dateFrom, filters.dateTo],
    queryFn: () =>
      api.permits.list({
        period: filters.dateFrom ? undefined : filters.period,
        date_from: filters.dateFrom,
        date_to: filters.dateTo,
        zip: filters.zip,
        builder: filters.builder,
        permit_type: filters.permitType,
        use_class: filters.useClass,
        years: filters.years?.join(",") || undefined,
        has_geo: true,
        limit: 5000,
      }),
  });

  useEffect(() => {
    if (!mapEl.current || mapRef.current) return;
    const map = L.map(mapEl.current, { zoomControl: true, attributionControl: true }).setView(HOUSTON_CENTER, 10);
    L.tileLayer("https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OSM</a> · <a href="https://carto.com/attributions">CARTO</a>',
    }).addTo(map);
    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const group = layerRef.current;
    if (!map || !group || !permits) return;

    // "New builds only" isolates new-construction permits from the ancillary
    // fire/site/sign/trade sub-permits that share the same project.
    const shown = filters.newBuildsOnly
      ? permits.filter((p) => p.permit_nature === "new_building")
      : permits;

    group.clearLayers();
    if (heatRef.current) {
      map.removeLayer(heatRef.current);
      heatRef.current = null;
    }

    if (showHeat && shown.length) {
      const heatData = shown
        .filter((p) => p.latitude && p.longitude)
        .map((p) => [p.latitude!, p.longitude!, 0.6]);
      heatRef.current = (L as any).heatLayer(heatData, {
        radius: 18,
        blur: 22,
        maxZoom: 14,
        gradient: { 0.0: "#1e3a8a", 0.25: "#06b6d4", 0.5: "#facc15", 0.75: "#f97316", 1.0: "#ef4444" },
      }).addTo(map);
    }

    if (showPins) {
      const today = Date.now();
      for (const p of shown) {
        if (!p.latitude || !p.longitude) continue;
        const daysAgo = p.permit_date ? Math.floor((today - new Date(p.permit_date).getTime()) / 86400000) : 999;
        let color = recencyColor(daysAgo);
        if (colorMode === "builder") color = builderColor(p.builder);
        else if (colorMode === "useClass") color = useClassColor(p.use_class);

        const marker = L.circleMarker([p.latitude, p.longitude], {
          radius: 4,
          color,
          weight: 1,
          fillColor: color,
          fillOpacity: 0.85,
        });
        marker.on("click", () => setSelectedPermit(p));
        marker.addTo(group);
      }
    }

    // When focused on a single builder (e.g. clicked from the leaderboard),
    // pan/zoom the map to that builder's permits so they're actually visible.
    if (filters.builder) {
      const pts = shown
        .filter((p) => p.latitude && p.longitude)
        .map((p) => [p.latitude!, p.longitude!] as [number, number]);
      if (pts.length) {
        map.fitBounds(L.latLngBounds(pts), { padding: [40, 40], maxZoom: 14 });
      }
    }
  }, [permits, colorMode, showHeat, showPins, filters.builder, filters.newBuildsOnly]);

  return (
    <div className="relative h-full w-full">
      <div ref={mapEl} className="absolute inset-0" />

      {/* Control panel */}
      <div className="absolute right-3 top-3 z-[400] flex flex-col gap-2">
        <div className="rounded-md border border-border bg-popover/90 p-1.5 backdrop-blur">
          <div className="flex items-center gap-1">
            <Button
              variant={showPins ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setShowPins((v) => !v)}
              className="h-7"
            >
              <MapPin className="h-3 w-3" />
              <span className="ml-1 text-[11px]">Pins</span>
            </Button>
            <Button
              variant={showHeat ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setShowHeat((v) => !v)}
              className="h-7"
            >
              <Flame className="h-3 w-3" />
              <span className="ml-1 text-[11px]">Heat</span>
            </Button>
            <Button
              variant={filters.newBuildsOnly ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setFilter("newBuildsOnly", !filters.newBuildsOnly)}
              className="h-7"
              title="Show only new-construction permits (hide fire/site/sign/trade sub-permits)"
            >
              <Building2 className="h-3 w-3" />
              <span className="ml-1 text-[11px]">New builds</span>
            </Button>
          </div>
        </div>
        <div className="rounded-md border border-border bg-popover/90 p-1.5 backdrop-blur">
          <div className="px-1 pb-1 text-[9px] uppercase tracking-widest text-muted-foreground">Color by</div>
          <div className="flex flex-col gap-0.5">
            {(["recency", "builder", "useClass"] as ColorMode[]).map((m) => (
              <button
                key={m}
                onClick={() => setColorMode(m)}
                className={cn(
                  "rounded px-1.5 py-0.5 text-left text-[11px] transition-colors",
                  colorMode === m ? "bg-secondary text-foreground" : "text-muted-foreground hover:bg-secondary/60"
                )}
              >
                {m === "useClass" ? "Use class" : m[0].toUpperCase() + m.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Live count */}
      <div className="absolute bottom-3 left-3 z-[400] rounded-md border border-border bg-popover/90 px-2 py-1.5 text-[11px] backdrop-blur">
        <span className="num font-medium text-foreground">
          {(filters.newBuildsOnly
            ? permits?.filter((p) => p.permit_nature === "new_building").length
            : permits?.length) ?? 0}
        </span>
        <span className="ml-1 text-muted-foreground">
          {filters.newBuildsOnly ? "new-build permits in view" : "permits in view"}
        </span>
      </div>

      {/* Legend (bottom-left, above the live count) */}
      <div className="absolute bottom-12 left-3 z-[400] max-w-[220px]">
        <MapLegend colorMode={colorMode} showHeat={showHeat} showPins={showPins} />
      </div>

      {/* Builder profile drawer (opened from pin builder name link) */}
      <BuilderDetailDrawer
        builder={detailBuilder}
        onClose={() => setDetailBuilder(null)}
      />

      {/* Detail drawer */}
      {selectedPermit && (
        <div className="absolute bottom-3 right-3 z-[400] w-72 rounded-md border border-border bg-popover/95 p-3 shadow-xl backdrop-blur">
          <div className="mb-1 flex items-start justify-between gap-2">
            <div className="flex-1">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                {selectedPermit.permit_type} · {selectedPermit.zip_code}
              </div>
              <div className="text-xs font-semibold">{selectedPermit.address || "—"}</div>
            </div>
            <button
              onClick={() => setSelectedPermit(null)}
              className="text-muted-foreground hover:text-foreground"
            >
              ×
            </button>
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
            <div className="text-muted-foreground">Date</div>
            <div className="num">{selectedPermit.permit_date}</div>
            <div className="text-muted-foreground">Builder</div>
            <div className="truncate">
              {selectedPermit.builder ? (
                <button
                  className="text-foreground underline-offset-2 hover:underline"
                  onClick={() => {
                    setDetailBuilder(selectedPermit.builder!);
                  }}
                  title="View builder profile"
                >
                  {selectedPermit.builder}
                </button>
              ) : selectedPermit.appraisal_status === "pending" ? (
                <span className="italic text-muted-foreground">Appraisal pending</span>
              ) : (
                "—"
              )}
            </div>
            <div className="text-muted-foreground">Sq ft</div>
            <div className="num">
              {selectedPermit.square_feet?.toLocaleString() ??
                (selectedPermit.appraisal_status === "pending" ? (
                  <span className="italic text-muted-foreground">Appraisal pending</span>
                ) : (
                  "—"
                ))}
            </div>
            <div className="text-muted-foreground">Use</div>
            <div>
              {!selectedPermit.use_class || selectedPermit.use_class === "general" ? (
                <span className="italic text-muted-foreground">Unknown/Pending/General</span>
              ) : (
                <>
                  {selectedPermit.use_class}
                  {selectedPermit.use_class_assumed && (
                    <span
                      className="ml-0.5 cursor-help text-muted-foreground"
                      title="Assumed from the permit name — no structured use data yet; refined as data posts"
                    >
                      *
                    </span>
                  )}
                </>
              )}
            </div>
          </div>
          {selectedPermit.comments && (
            <div className="mt-2 line-clamp-2 border-t border-border pt-2 text-[10px] text-muted-foreground">
              {selectedPermit.comments}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
