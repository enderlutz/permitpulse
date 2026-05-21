import { Plus, RefreshCw, Save, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AddWidgetMenu } from "./AddWidgetMenu";
import { useWorkspace } from "@/store/workspace";
import { WIDGETS } from "./registry";

interface Props {
  page: string;
  title: string;
  subtitle?: string;
  defaultLayout?: () => void;
}

export function PageHeader({ page, title, subtitle, defaultLayout }: Props) {
  const ws = useWorkspace((s) => s.byPage[page]);
  const addWidget = useWorkspace((s) => s.addWidget);

  const widgetCount = ws?.widgets.length ?? 0;

  return (
    <div className="flex items-center justify-between border-b border-border bg-surface/40 px-4 py-2">
      <div className="flex items-baseline gap-3">
        <h1 className="text-base font-semibold tracking-tight">{title}</h1>
        {subtitle && <span className="text-xs text-muted-foreground">{subtitle}</span>}
        <Badge variant="outline" className="text-[10px]">
          {widgetCount} {widgetCount === 1 ? "widget" : "widgets"}
        </Badge>
      </div>
      <div className="flex items-center gap-2">
        {defaultLayout && (
          <Button variant="ghost" size="sm" onClick={defaultLayout} className="gap-1.5">
            <RotateCcw className="h-3 w-3" />
            Reset
          </Button>
        )}
        <AddWidgetMenu onAdd={(type) => addWidget(page, type, WIDGETS[type]?.title)} />
      </div>
    </div>
  );
}
