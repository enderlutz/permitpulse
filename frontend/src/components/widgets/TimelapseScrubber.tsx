import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Play, Pause, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { useWorkspace } from "@/store/workspace";
import { cn } from "@/lib/utils";

export function TimelapseScrubber() {
  const period = useWorkspace((s) => s.filters.period);
  const setFilter = useWorkspace((s) => s.setFilter);
  const { data } = useQuery({
    queryKey: ["timeseries", period],
    queryFn: () => api.analytics.timeseries({ period, bucket: "week" }),
  });

  const buckets = useMemo(() => data ?? [], [data]);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  // Track whether the user has actively interacted with the scrubber.
  // Without this guard, the widget would set dateFrom/dateTo on mount to
  // the latest week — hijacking every other widget's filters before the
  // user even knew this widget existed. Stays inert until Play or scrub.
  const [userDriven, setUserDriven] = useState(false);
  const timerRef = useRef<number | null>(null);

  // Reset to end when data loads
  useEffect(() => {
    if (buckets.length) setIndex(buckets.length - 1);
  }, [buckets.length]);

  // Clear hijacked filters when this widget unmounts or user resets
  useEffect(() => {
    return () => {
      if (userDriven) {
        setFilter("dateFrom", null);
        setFilter("dateTo", null);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!playing || !buckets.length) return;
    timerRef.current = window.setInterval(() => {
      setIndex((i) => {
        const next = i + 1;
        if (next >= buckets.length) {
          setPlaying(false);
          return buckets.length - 1;
        }
        return next;
      });
    }, 500 / speed);
    return () => {
      if (timerRef.current !== null) window.clearInterval(timerRef.current);
    };
  }, [playing, speed, buckets.length]);

  const current = buckets[index];
  const max = useMemo(() => Math.max(1, ...buckets.map((b) => b.count)), [buckets]);

  // Push filter to date range based on current bucket — ONLY when user
  // has actively engaged the scrubber. Otherwise the widget would hijack
  // the global filters on mount and the map would show only the latest week.
  useEffect(() => {
    if (!userDriven || !current) return;
    const m = current.bucket.match(/(\d{4})-W(\d{2})/);
    if (!m) return;
    const year = parseInt(m[1]);
    const week = parseInt(m[2]);
    const jan4 = new Date(Date.UTC(year, 0, 4));
    const start = new Date(jan4);
    start.setUTCDate(jan4.getUTCDate() - jan4.getUTCDay() + 1 + (week - 1) * 7);
    const end = new Date(start);
    end.setUTCDate(start.getUTCDate() + 6);
    setFilter("dateFrom", start.toISOString().slice(0, 10));
    setFilter("dateTo", end.toISOString().slice(0, 10));
  }, [index, current, setFilter, userDriven]);

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex items-center gap-2">
        <Button
          variant={playing ? "secondary" : "default"}
          size="icon"
          onClick={() => {
            setUserDriven(true);
            setPlaying((p) => !p);
          }}
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => {
            // Reset clears the hijacked filters and goes back to "no scrubbing"
            setUserDriven(false);
            setFilter("dateFrom", null);
            setFilter("dateTo", null);
            setIndex(buckets.length ? buckets.length - 1 : 0);
            setPlaying(false);
          }}
          aria-label="Restart"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </Button>
        <div className="flex items-center gap-1">
          {[1, 2, 4].map((s) => (
            <button
              key={s}
              onClick={() => setSpeed(s)}
              className={cn(
                "rounded px-1.5 py-0.5 text-[10px]",
                speed === s ? "bg-secondary text-foreground" : "text-muted-foreground hover:bg-secondary/60"
              )}
            >
              {s}×
            </button>
          ))}
        </div>
        <div className="flex-1 text-right">
          <div className="num text-xs font-semibold">{current?.bucket || "—"}</div>
          <div className="num text-[10px] text-muted-foreground">
            {current?.count ?? 0} permits this week
          </div>
        </div>
      </div>

      <div className="relative flex-1">
        <div className="absolute inset-0 flex items-end gap-px">
          {buckets.map((b, i) => (
            <button
              key={b.bucket}
              onClick={() => {
                setUserDriven(true);
                setIndex(i);
                setPlaying(false);
              }}
              className={cn(
                "flex-1 rounded-t transition-all hover:opacity-90",
                i === index ? "bg-primary" : i < index ? "bg-primary/40" : "bg-secondary"
              )}
              style={{ height: `${(b.count / max) * 100}%` }}
              title={`${b.bucket}: ${b.count}`}
            />
          ))}
        </div>
      </div>

      <input
        type="range"
        min={0}
        max={Math.max(0, buckets.length - 1)}
        value={index}
        onChange={(e) => {
          setUserDriven(true);
          setIndex(parseInt(e.target.value));
          setPlaying(false);
        }}
        className="h-1 w-full appearance-none rounded-full bg-secondary accent-primary"
      />
    </div>
  );
}
