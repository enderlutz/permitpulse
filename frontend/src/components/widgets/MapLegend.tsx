import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { BUILDER_COLORS, HEAT_GRADIENT, recencyColor, useClassColor } from "@/lib/colors";

type ColorMode = "recency" | "builder" | "useClass";

interface LegendProps {
  colorMode: ColorMode;
  showHeat: boolean;
  showPins: boolean;
}

const RECENCY_BUCKETS: { label: string; days: number }[] = [
  { label: "≤ 7 days", days: 0 },
  { label: "8 – 30 days", days: 14 },
  { label: "1 – 3 months", days: 60 },
  { label: "3 – 6 months", days: 120 },
  { label: "> 6 months", days: 240 },
];

const USE_CLASSES: string[] = [
  "residential",
  "apartment",
  "warehouse",
  "retail",
  "restaurant",
  "office",
];

// Heatmap gradient — surfaced from HEAT_GRADIENT in colors.ts and rendered as
// a CSS linear-gradient so the legend stays visually identical to the actual
// layer even if the gradient stops change.
const HEAT_CSS = `linear-gradient(to right, ${Object.entries(HEAT_GRADIENT)
  .sort(([a], [b]) => parseFloat(a) - parseFloat(b))
  .map(([stop, color]) => `${color} ${parseFloat(stop) * 100}%`)
  .join(", ")})`;

export function MapLegend({ colorMode, showHeat, showPins }: LegendProps) {
  const [open, setOpen] = useState(true);

  // Show top 10 builders in the legend — keeps it readable. The leaderboard
  // widget is where users go for the full picture.
  const builderRows = Object.entries(BUILDER_COLORS).slice(0, 10);

  return (
    <div className="rounded-md border border-border bg-popover/90 text-[11px] shadow-md backdrop-blur">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-2 py-1.5 text-muted-foreground hover:text-foreground"
        title={open ? "Collapse legend" : "Expand legend"}
      >
        <span className="text-[9px] font-medium uppercase tracking-widest">Legend</span>
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />}
      </button>

      {open && (
        <div className="border-t border-border/60 px-2 py-2">
          {/* Pin coloring */}
          {showPins && (
            <div className="mb-2">
              <div className="mb-1 text-[9px] font-medium uppercase tracking-wider text-muted-foreground">
                Pins · colored by{" "}
                <span className="text-foreground">
                  {colorMode === "useClass" ? "use class" : colorMode}
                </span>
              </div>
              {colorMode === "recency" && (
                <LegendRows
                  rows={RECENCY_BUCKETS.map((b) => ({
                    label: b.label,
                    color: recencyColor(b.days),
                  }))}
                />
              )}
              {colorMode === "builder" && (
                <>
                  <LegendRows
                    rows={builderRows.map(([name, color]) => ({ label: name, color }))}
                  />
                  <div className="mt-1 flex items-center gap-1.5 text-[10px] text-muted-foreground/70">
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: "#64748b" }} />
                    <span>Other / unclassified</span>
                  </div>
                </>
              )}
              {colorMode === "useClass" && (
                <LegendRows
                  rows={USE_CLASSES.map((u) => ({
                    label: u[0].toUpperCase() + u.slice(1),
                    color: useClassColor(u),
                  }))}
                />
              )}
            </div>
          )}

          {/* Heatmap */}
          {showHeat && (
            <div className={cn(showPins && "border-t border-border/60 pt-2")}>
              <div className="mb-1 text-[9px] font-medium uppercase tracking-wider text-muted-foreground">
                Heatmap density
              </div>
              <div className="flex h-2 w-full rounded" style={{ background: HEAT_CSS }} />
              <div className="mt-0.5 flex justify-between text-[9px] text-muted-foreground">
                <span>Few permits</span>
                <span>Many permits</span>
              </div>
            </div>
          )}

          {!showPins && !showHeat && (
            <div className="text-[10px] italic text-muted-foreground">
              Toggle Pins or Heat to see colors
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function LegendRows({ rows }: { rows: { label: string; color: string }[] }) {
  return (
    <div className="flex flex-col gap-0.5">
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-1.5">
          <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: r.color }} />
          <span className="truncate text-[10px] text-foreground/85">{r.label}</span>
        </div>
      ))}
    </div>
  );
}
