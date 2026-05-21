import { Plus } from "lucide-react";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { widgetCategories } from "./registry";

interface Props {
  onAdd: (type: string) => void;
}

export function AddWidgetMenu({ onAdd }: Props) {
  const cats = widgetCategories();
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <Plus className="h-3.5 w-3.5" />
          Add Widget
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <ScrollArea className="max-h-96">
          <div className="p-2">
            {cats.map((c) =>
              c.widgets.length ? (
                <div key={c.id} className="mb-2 last:mb-0">
                  <div className="px-2 py-1 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                    {c.label}
                  </div>
                  {c.widgets.map((w) => (
                    <button
                      key={w.type}
                      onClick={() => onAdd(w.type)}
                      className="flex w-full flex-col items-start gap-0.5 rounded-md px-2 py-1.5 text-left hover:bg-secondary"
                    >
                      <span className="text-xs font-medium">{w.title}</span>
                      <span className="text-[11px] leading-snug text-muted-foreground">{w.description}</span>
                    </button>
                  ))}
                </div>
              ) : null
            )}
          </div>
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}
