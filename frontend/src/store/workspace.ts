import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Layout } from "react-grid-layout";

export interface WidgetInstance {
  id: string;          // instance id
  type: string;        // widget registry key
  title?: string;
  config?: Record<string, any>;
}

export interface PageWorkspace {
  widgets: WidgetInstance[];
  layout: Layout[];
}

export interface FiltersState {
  period: "7d" | "30d" | "90d" | "12mo";
  zip: string | null;
  builder: string | null;
  permitType: string | null;
  dateFrom: string | null;
  dateTo: string | null;
}

interface WorkspaceState {
  byPage: Record<string, PageWorkspace>;
  filters: FiltersState;
  setLayout: (page: string, layout: Layout[]) => void;
  addWidget: (page: string, type: string, title?: string) => void;
  removeWidget: (page: string, id: string) => void;
  resetPage: (page: string, ws: PageWorkspace) => void;
  setFilter: <K extends keyof FiltersState>(k: K, v: FiltersState[K]) => void;
  clearFilters: () => void;
}

const defaultFilters: FiltersState = {
  period: "90d",
  zip: null,
  builder: null,
  permitType: null,
  dateFrom: null,
  dateTo: null,
};

export const useWorkspace = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      byPage: {},
      filters: defaultFilters,
      setLayout: (page, layout) =>
        set((s) => ({
          byPage: { ...s.byPage, [page]: { ...(s.byPage[page] ?? { widgets: [], layout: [] }), layout } },
        })),
      addWidget: (page, type, title) =>
        set((s) => {
          const ws = s.byPage[page] ?? { widgets: [], layout: [] };
          const id = `${type}-${Date.now().toString(36)}`;
          const nextWidgets = [...ws.widgets, { id, type, title }];
          const maxY = ws.layout.reduce((m, l) => Math.max(m, l.y + l.h), 0);
          const nextLayout = [...ws.layout, { i: id, x: 0, y: maxY, w: 6, h: 6, minW: 3, minH: 3 }];
          return { byPage: { ...s.byPage, [page]: { widgets: nextWidgets, layout: nextLayout } } };
        }),
      removeWidget: (page, id) =>
        set((s) => {
          const ws = s.byPage[page];
          if (!ws) return s;
          return {
            byPage: {
              ...s.byPage,
              [page]: {
                widgets: ws.widgets.filter((w) => w.id !== id),
                layout: ws.layout.filter((l) => l.i !== id),
              },
            },
          };
        }),
      resetPage: (page, ws) =>
        set((s) => ({ byPage: { ...s.byPage, [page]: ws } })),
      setFilter: (k, v) => set((s) => ({ filters: { ...s.filters, [k]: v } })),
      clearFilters: () => set({ filters: defaultFilters }),
    }),
    { name: "permit-pulse-workspace-v1" }
  )
);
