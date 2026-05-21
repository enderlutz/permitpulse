import { GripVertical, MoreVertical, X, Maximize2 } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown";

interface Props {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  onRemove?: () => void;
  actions?: React.ReactNode;
  noPadding?: boolean;
}

export function WidgetFrame({ title, subtitle, children, onRemove, actions, noPadding }: Props) {
  const [maximized, setMaximized] = useState(false);
  return (
    <div
      className={cn(
        "group flex h-full w-full flex-col overflow-hidden rounded-lg border border-border bg-card",
        maximized && "fixed inset-4 z-40 shadow-2xl"
      )}
    >
      <div className="widget-handle flex h-8 shrink-0 cursor-move items-center justify-between gap-2 border-b border-border bg-surface/60 px-2.5">
        <div className="flex min-w-0 items-center gap-1.5">
          <GripVertical className="h-3 w-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-50" />
          <span className="truncate text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            {title}
          </span>
          {subtitle && <span className="truncate text-[10px] text-muted-foreground/70">· {subtitle}</span>}
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          {actions}
          <button
            onClick={() => setMaximized((m) => !m)}
            className="rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-surface-raised hover:text-foreground group-hover:opacity-100"
            aria-label="Maximize"
          >
            <Maximize2 className="h-3 w-3" />
          </button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-surface-raised hover:text-foreground group-hover:opacity-100"
                aria-label="Widget options"
              >
                <MoreVertical className="h-3 w-3" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={() => setMaximized((m) => !m)}>
                {maximized ? "Restore" : "Maximize"}
              </DropdownMenuItem>
              {onRemove && (
                <DropdownMenuItem onSelect={onRemove} className="text-destructive">
                  <X className="h-3 w-3" /> Remove
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      <div className={cn("flex-1 overflow-hidden", !noPadding && "p-3")}>{children}</div>
    </div>
  );
}
