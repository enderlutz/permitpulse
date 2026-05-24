import type {
  Permit,
  HotspotZip,
  BuilderRow,
  KpiSummary,
  TimeseriesPoint,
  TypeMixRow,
  OpportunityPreset,
} from "./types";

// Production fallback so the prod URL always resolves correctly even if the
// Vercel env var isn't set or a stale HTML caches an old bundle hash. Local
// dev (running on localhost) still uses the Vite proxy at /api.
const PROD_FALLBACK = "https://permitpulse-production.up.railway.app/api";
const onLocalhost = typeof window !== "undefined" && /localhost|127\.0\.0\.1/.test(window.location.hostname);

function normalizeApiBase(raw: string | undefined): string {
  if (!raw) return onLocalhost ? "/api" : PROD_FALLBACK;
  let v = raw.trim().replace(/\/+$/, "");
  // Relative paths (start with /) are fine — preserved as-is.
  if (v.startsWith("/")) return v;
  // If someone set the env var without a protocol (e.g.
  // "permitpulse-production.up.railway.app/api"), the browser would treat it
  // as a relative path and the request would hit the Vercel SPA fallback.
  // Prepend https:// so it always resolves to an absolute origin.
  if (!/^https?:\/\//i.test(v)) v = `https://${v}`;
  return v;
}

export const API_BASE = normalizeApiBase(import.meta.env.VITE_API_BASE);

// Expose at runtime so we can debug "blank UI in prod" cases without devtools.
if (typeof window !== "undefined") {
  (window as any).__PERMITPULSE__ = { API_BASE };
}

async function fetchJSON<T>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`;
  try {
    const r = await fetch(url);
    if (!r.ok) {
      console.error(`[API] ${r.status} ${r.statusText}`, url);
      throw new Error(`${r.status} ${r.statusText} – ${path}`);
    }
    const data = await r.json();
    console.debug(`[API] ${r.status}`, path, Array.isArray(data) ? `(${data.length} rows)` : "(obj)");
    return data;
  } catch (err) {
    console.error(`[API] fetch failed`, url, err);
    throw err;
  }
}

export const api = {
  permits: {
    list: (params: Record<string, any> = {}) =>
      fetchJSON<Permit[]>(`/permits?${qs(params)}`),
    recent: (days = 30, limit = 50) =>
      fetchJSON<Permit[]>(`/permits/recent?days=${days}&limit=${limit}`),
    detail: (id: number) => fetchJSON<Permit>(`/permits/${id}`),
    types: () => fetchJSON<{ type: string; count: number }[]>(`/permits/types`),
    years: () => fetchJSON<{ year: number; count: number }[]>(`/permits/years`),
    meta: () => fetchJSON<{
      latest_ingest: string | null;
      latest_permit_date: string | null;
      total: number;
      geocoded: number;
    }>(`/permits/meta`),
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
    leaderboard: (period = "30d", limit = 10, tiers?: string[]) => {
      const t = tiers && tiers.length ? `&tiers=${tiers.join(",")}` : "";
      return fetchJSON<BuilderRow[]>(`/builders/leaderboard?period=${period}&limit=${limit}${t}`);
    },
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
