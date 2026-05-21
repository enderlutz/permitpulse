import { useMemo } from "react";
import GridLayout, { Responsive, WidthProvider, type Layout } from "react-grid-layout";
import { useWorkspace } from "@/store/workspace";
import { WIDGETS } from "./registry";
import { WidgetFrame } from "./WidgetFrame";

const ResponsiveGrid = WidthProvider(Responsive);

interface Props {
  page: string;
}

export function WorkspaceGrid({ page }: Props) {
  const ws = useWorkspace((s) => s.byPage[page]);
  const setLayout = useWorkspace((s) => s.setLayout);
  const removeWidget = useWorkspace((s) => s.removeWidget);

  const layout = ws?.layout ?? [];

  if (!ws || ws.widgets.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="grid-bg rounded-lg border border-dashed border-border p-12 text-center">
          <p className="text-sm text-muted-foreground">This page has no widgets yet.</p>
          <p className="text-xs text-muted-foreground/70">Use the + Add Widget button to start building.</p>
        </div>
      </div>
    );
  }

  return (
    <ResponsiveGrid
      className="layout"
      layouts={{ lg: layout }}
      breakpoints={{ lg: 1024, md: 768, sm: 480 }}
      cols={{ lg: 12, md: 12, sm: 6 }}
      rowHeight={48}
      margin={[10, 10]}
      containerPadding={[12, 12]}
      draggableHandle=".widget-handle"
      isResizable
      isDraggable
      onLayoutChange={(l) => setLayout(page, l)}
      compactType="vertical"
    >
      {ws.widgets.map((widget) => {
        const def = WIDGETS[widget.type];
        if (!def) return <div key={widget.id}>Unknown widget: {widget.type}</div>;
        const Comp = def.component;
        return (
          <div key={widget.id} className="overflow-hidden">
            <WidgetFrame
              title={widget.title || def.title}
              onRemove={() => removeWidget(page, widget.id)}
            >
              <Comp config={widget.config} />
            </WidgetFrame>
          </div>
        );
      })}
    </ResponsiveGrid>
  );
}
