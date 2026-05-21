// Builder color mapping — keep in sync with backend/scripts/seed_builders.py
export const BUILDER_COLORS: Record<string, string> = {
  "D.R. Horton": "#ef4444",
  "Perry Homes": "#f59e0b",
  "K. Hovnanian Homes": "#a855f7",
  Lennar: "#06b6d4",
  "Meritage Homes": "#84cc16",
  "Toll Brothers": "#f43f5e",
  "David Weekley Homes": "#22c55e",
  "Highland Homes": "#8b5cf6",
  "Trendmaker Homes": "#3b82f6",
  "Coventry Homes": "#10b981",
};

export const builderColor = (b?: string | null) => (b && BUILDER_COLORS[b]) || "#94a3b8";

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
