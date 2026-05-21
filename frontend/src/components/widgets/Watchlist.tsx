import { useState, useEffect } from "react";
import { Bookmark, X, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useWorkspace } from "@/store/workspace";
import { cn } from "@/lib/utils";

interface WatchItem {
  type: "zip" | "builder";
  value: string;
  addedAt: number;
}

function readWatch(): WatchItem[] {
  try {
    return JSON.parse(localStorage.getItem("hb-watchlist") || "[]");
  } catch {
    return [];
  }
}

function writeWatch(items: WatchItem[]) {
  localStorage.setItem("hb-watchlist", JSON.stringify(items));
}

export function Watchlist() {
  const [items, setItems] = useState<WatchItem[]>([]);
  const [newKind, setNewKind] = useState<"zip" | "builder">("zip");
  const [newVal, setNewVal] = useState("");
  const setFilter = useWorkspace((s) => s.setFilter);

  useEffect(() => {
    setItems(readWatch());
  }, []);

  const add = () => {
    if (!newVal.trim()) return;
    const next = [...items, { type: newKind, value: newVal.trim(), addedAt: Date.now() }];
    setItems(next);
    writeWatch(next);
    setNewVal("");
  };
  const remove = (i: number) => {
    const next = items.filter((_, idx) => idx !== i);
    setItems(next);
    writeWatch(next);
  };

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex items-center gap-1">
        <div className="flex rounded-md border border-border">
          {(["zip", "builder"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setNewKind(k)}
              className={cn(
                "px-2 py-1 text-[10px] uppercase tracking-wider",
                newKind === k ? "bg-secondary text-foreground" : "text-muted-foreground"
              )}
            >
              {k}
            </button>
          ))}
        </div>
        <input
          value={newVal}
          onChange={(e) => setNewVal(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder={newKind === "zip" ? "77079" : "D.R. Horton"}
          className="h-7 flex-1 rounded-md border border-border bg-surface px-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <Button variant="outline" size="icon" onClick={add}>
          <Plus className="h-3 w-3" />
        </Button>
      </div>

      <div className="flex-1 space-y-1 overflow-auto pr-1">
        {items.length === 0 && (
          <div className="flex h-full items-center justify-center text-center text-xs text-muted-foreground">
            <div>
              <Bookmark className="mx-auto mb-1 h-4 w-4 opacity-50" />
              No items saved yet. <br /> Track ZIPs or builders here.
            </div>
          </div>
        )}
        {items.map((item, i) => (
          <div
            key={i}
            className="group flex items-center justify-between gap-2 rounded border border-border bg-surface/40 px-2 py-1.5"
          >
            <button
              onClick={() =>
                item.type === "zip"
                  ? setFilter("zip", item.value)
                  : setFilter("builder", item.value)
              }
              className="flex flex-1 items-center gap-2 text-left"
            >
              <span className="rounded bg-secondary px-1 py-0.5 text-[9px] uppercase tracking-widest text-muted-foreground">
                {item.type}
              </span>
              <span className="num text-xs">{item.value}</span>
            </button>
            <button
              onClick={() => remove(i)}
              className="text-muted-foreground opacity-0 hover:text-destructive group-hover:opacity-100"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
