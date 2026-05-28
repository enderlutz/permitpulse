// Builder color mapping — keyed by canonical_builder. Ordered by actual
// 90-day footprint in Houston permit data (top entries dominate the map).
// Smaller/regional builders fall through to a hash-based palette below so
// every non-canonicalized name still gets a stable color.
export const BUILDER_COLORS: Record<string, string> = {
  "D.R. Horton": "#ef4444",
  "Meritage Homes": "#84cc16",
  "K. Hovnanian Homes": "#a855f7",
  "LGI Homes": "#06b6d4",
  "Starlight Homes": "#f59e0b",
  "First America Homes": "#22c55e",
  "Perry Homes": "#f43f5e",
  "Saratoga Homes": "#3b82f6",
  "Newmark Homes": "#10b981",
  Lennar: "#0ea5e9",
  "Century Communities": "#eab308",
  "Beazer Homes": "#ec4899",
  "Toll Brothers": "#f97316",
  "David Weekley Homes": "#8b5cf6",
  "Highland Homes": "#14b8a6",
  "Trendmaker Homes": "#6366f1",
  "Coventry Homes": "#06d6a0",
};

// Stable fallback palette for builders not in BUILDER_COLORS (any non-canonical
// or smaller local entity). Uses simple string hash → palette index so the
// same builder gets the same color across re-renders.
const FALLBACK_PALETTE = [
  "#64748b", "#71717a", "#78716c", "#737373", "#6b7280",
  "#94a3b8", "#a1a1aa", "#a8a29e", "#a3a3a3", "#9ca3af",
];

function hashStr(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export const builderColor = (b?: string | null): string => {
  if (!b) return "#64748b";
  if (BUILDER_COLORS[b]) return BUILDER_COLORS[b];
  return FALLBACK_PALETTE[hashStr(b) % FALLBACK_PALETTE.length];
};

// Recency → color (newer = greener)
export const recencyColor = (daysAgo: number): string => {
  if (daysAgo <= 7) return "#10b981";       // emerald (hot, this week)
  if (daysAgo <= 30) return "#34d399";      // mint
  if (daysAgo <= 90) return "#fbbf24";      // amber
  if (daysAgo <= 180) return "#f97316";     // orange
  return "#64748b";                          // slate (older)
};

// Use class → color
export const useClassColor = (uc?: string | null): string => {
  switch (uc) {
    case "residential": return "#10b981";
    case "warehouse": return "#06b6d4";
    case "retail": return "#a855f7";
    case "restaurant": return "#f59e0b";
    case "office": return "#3b82f6";
    case "apartment": return "#ec4899";
    default: return "#64748b";
  }
};

// Heatmap gradient stops (cold → hot)
export const HEAT_GRADIENT = {
  0.0: "#1e3a8a",   // deep blue
  0.25: "#06b6d4",  // cyan
  0.5: "#facc15",   // yellow
  0.75: "#f97316",  // orange
  1.0: "#ef4444",   // red
};
