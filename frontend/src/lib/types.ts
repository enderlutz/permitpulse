export interface Permit {
  id: number;
  project_no: string;
  permit_date: string | null;
  permit_type: string | null;
  address: string | null;
  zip_code: string | null;
  comments: string | null;
  builder: string | null;
  project_value: number | null;
  square_feet: number | null;
  use_class: string | null;
  latitude: number | null;
  longitude: number | null;
  source: string | null;
  appraisal_status: "matched" | "pending" | null;
  permit_nature:
    | "new_building"
    | "remodel"
    | "fire"
    | "mep"
    | "site_civil"
    | "sign"
    | "demolition"
    | null;
}

export interface HotspotZip {
  zip_code: string;
  permit_count: number;
  velocity_pct: number;
  avg_value: number | null;
  score: number;
  sparkline: number[];
}

export interface BuilderRow {
  builder: string;
  permit_count: number;
  tier?: "national" | "local" | "individual" | "unknown" | null;
}

export interface KpiSummary {
  permits_this_period: number;
  permits_prev_period: number;
  velocity_pct: number;
  hotspot_count: number;
  top_zip: string | null;
  top_zip_count: number;
  top_builder: string | null;
  top_builder_count: number;
}

export interface TimeseriesPoint {
  bucket: string;
  count: number;
}

export interface TypeMixRow {
  type: string;
  count: number;
}

export interface OpportunityPreset {
  id: string;
  name: string;
  description: string;
}
