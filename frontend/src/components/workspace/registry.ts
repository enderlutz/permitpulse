import type { ComponentType } from "react";
import { MapWidget } from "@/components/widgets/MapWidget";
import { KPIStrip } from "@/components/widgets/KPIStrip";
import { BuilderLeaderboard } from "@/components/widgets/BuilderLeaderboard";
import { TrendingZips } from "@/components/widgets/TrendingZips";
import { HotspotScore } from "@/components/widgets/HotspotScore";
import { TimelapseScrubber } from "@/components/widgets/TimelapseScrubber";
import { OpportunityFinder } from "@/components/widgets/OpportunityFinder";
import { RecentPermits } from "@/components/widgets/RecentPermits";
import { TypeMixDonut } from "@/components/widgets/TypeMixDonut";
import { VolumeTrend } from "@/components/widgets/VolumeTrend";
import { BuilderCompare } from "@/components/widgets/BuilderCompare";
import { AIDigest } from "@/components/widgets/AIDigest";
import { Watchlist } from "@/components/widgets/Watchlist";
import { RiskPulse } from "@/components/widgets/RiskPulse";

export interface WidgetDef {
  type: string;
  title: string;
  category: "overview" | "map" | "builders" | "submarkets" | "opportunities" | "analytics";
  description: string;
  defaultSize: { w: number; h: number; minW?: number; minH?: number };
  component: ComponentType<{ config?: any }>;
}

export const WIDGETS: Record<string, WidgetDef> = {
  map: {
    type: "map",
    title: "Permit Map",
    category: "map",
    description: "Color-coded permit pins with heatmap, filters, and click-to-detail.",
    defaultSize: { w: 8, h: 10, minW: 4, minH: 6 },
    component: MapWidget,
  },
  kpis: {
    type: "kpis",
    title: "KPI Strip",
    category: "overview",
    description: "Period permit volume, velocity, top ZIP, top builder.",
    defaultSize: { w: 12, h: 3, minW: 6, minH: 2 },
    component: KPIStrip,
  },
  builderLeaderboard: {
    type: "builderLeaderboard",
    title: "Top Builders",
    category: "builders",
    description: "Builders ranked by permit count in the selected period.",
    defaultSize: { w: 4, h: 6, minW: 3, minH: 4 },
    component: BuilderLeaderboard,
  },
  trendingZips: {
    type: "trendingZips",
    title: "Trending ZIPs",
    category: "submarkets",
    description: "ZIPs with highest activity and acceleration. Click to filter map.",
    defaultSize: { w: 4, h: 6, minW: 3, minH: 4 },
    component: TrendingZips,
  },
  hotspotScore: {
    type: "hotspotScore",
    title: "Hotspot Scores",
    category: "submarkets",
    description: "Composite ZIP ranking by volume + velocity + recency.",
    defaultSize: { w: 5, h: 8, minW: 4, minH: 5 },
    component: HotspotScore,
  },
  timelapse: {
    type: "timelapse",
    title: "Time-lapse Scrubber",
    category: "analytics",
    description: "Drag through time to watch permits appear chronologically.",
    defaultSize: { w: 12, h: 3, minW: 6, minH: 2 },
    component: TimelapseScrubber,
  },
  opportunities: {
    type: "opportunities",
    title: "Opportunity Finder",
    category: "opportunities",
    description: "Run preset queries to surface market gaps and emerging zones.",
    defaultSize: { w: 6, h: 7, minW: 4, minH: 5 },
    component: OpportunityFinder,
  },
  recentPermits: {
    type: "recentPermits",
    title: "Recent Permits",
    category: "overview",
    description: "Live feed of the most recent permits with type and ZIP.",
    defaultSize: { w: 4, h: 8, minW: 3, minH: 4 },
    component: RecentPermits,
  },
  typeMix: {
    type: "typeMix",
    title: "Permit Type Mix",
    category: "analytics",
    description: "Donut chart of permit categories for the selected period.",
    defaultSize: { w: 4, h: 6, minW: 3, minH: 4 },
    component: TypeMixDonut,
  },
  volumeTrend: {
    type: "volumeTrend",
    title: "Volume Trend",
    category: "analytics",
    description: "Weekly permit count line chart over the selected period.",
    defaultSize: { w: 8, h: 6, minW: 4, minH: 4 },
    component: VolumeTrend,
  },
  builderCompare: {
    type: "builderCompare",
    title: "Builder vs Builder",
    category: "builders",
    description: "Compare 2-3 builders' permit footprints and submarkets.",
    defaultSize: { w: 6, h: 7, minW: 4, minH: 5 },
    component: BuilderCompare,
  },
  aiDigest: {
    type: "aiDigest",
    title: "AI Weekly Digest",
    category: "overview",
    description: "Claude-generated narrative of notable activity this week.",
    defaultSize: { w: 6, h: 5, minW: 4, minH: 4 },
    component: AIDigest,
  },
  watchlist: {
    type: "watchlist",
    title: "Watchlist",
    category: "overview",
    description: "Saved ZIPs and builders with new activity since last visit.",
    defaultSize: { w: 4, h: 7, minW: 3, minH: 4 },
    component: Watchlist,
  },
  riskPulse: {
    type: "riskPulse",
    title: "Risk Pulse",
    category: "opportunities",
    description: "Cooling markets — previously active ZIPs that are decelerating.",
    defaultSize: { w: 5, h: 6, minW: 4, minH: 4 },
    component: RiskPulse,
  },
};

export const widgetCategories = (): { id: string; label: string; widgets: WidgetDef[] }[] => {
  const grouped: Record<string, WidgetDef[]> = {};
  for (const w of Object.values(WIDGETS)) {
    (grouped[w.category] ||= []).push(w);
  }
  return [
    { id: "overview", label: "Overview" },
    { id: "map", label: "Map" },
    { id: "builders", label: "Builders" },
    { id: "submarkets", label: "Submarkets" },
    { id: "opportunities", label: "Opportunities" },
    { id: "analytics", label: "Analytics" },
  ].map((c) => ({ ...c, widgets: grouped[c.id] || [] }));
};
