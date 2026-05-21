import type {
  Permit,
  HotspotZip,
  BuilderRow,
  KpiSummary,
  TimeseriesPoint,
  TypeMixRow,
  OpportunityPreset,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";

async function fetchJSON<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} – ${path}`);
  return r.json();
}

export const api = {
  permits: {
    list: (params: Record<string, any> = {}) =>
      fetchJSON<Permit[]>(`/permits?${qs(params)}`),
    recent: (days = 30, limit = 50) =>
      fetchJSON<Permit[]>(`/permits/recent?days=${days}&limit=${limit}`),
    detail: (id: number) => fetchJSON<Permit>(`/permits/${id}`),
    types: () => fetchJSON<{ type: string; count: number }[]>(`/permits/types`),
  },
  analytics: {
    kpis: (period = "30d") => fetchJSON<KpiSummary>(`/analytics/kpis?period=${period}`),
    hotspots: (period = "90d", limit = 15) =>
      fetchJSON<HotspotZip[]>(`/analytics/hotspots?period=${period}&limit=${limit}`),
    timeseries: (params: Record<string, any> = {}) =>
      fetchJSON<TimeseriesPoint[]>(`/analytics/timeseries?${qs(params)}`),
    typeMix: (period = "90d") =>
      fetchJSON<TypeMixRow[]>(`/analytics/type-mix?period=${period}`),
  },
  builders: {
    leaderboard: (period = "30d", limit = 10) =>
      fetchJSON<BuilderRow[]>(`/builders/leaderboard?period=${period}&limit=${limit}`),
    footprint: (builder: string, period = "90d") =>
      fetchJSON<any>(`/builders/${encodeURIComponent(builder)}/footprint?period=${period}`),
  },
  opportunities: {
    presets: () => fetchJSON<OpportunityPreset[]>(`/opportunities/presets`),
    run: (presetId: string, limit = 10) =>
      fetchJSON<any[]>(`/opportunities/run/${presetId}?limit=${limit}`),
  },
};

function qs(params: Record<string, any>) {
  return Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join("&");
}
