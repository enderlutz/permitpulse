import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Map as MapIcon,
  HardHat,
  Building2,
  Lightbulb,
  ListChecks,
  Bookmark,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

type NavItem = { to: string; icon: typeof LayoutDashboard; label: string; end?: boolean };
const NAV: NavItem[] = [
  { to: "/", icon: LayoutDashboard, label: "Command Center", end: true },
  { to: "/map", icon: MapIcon, label: "Map" },
  { to: "/builders", icon: HardHat, label: "Builders" },
  { to: "/submarkets", icon: Building2, label: "Submarkets" },
  { to: "/opportunities", icon: Lightbulb, label: "Opportunities" },
  { to: "/permits", icon: ListChecks, label: "Permits" },
  { to: "/watchlist", icon: Bookmark, label: "Watchlist" },
];

export function Sidebar() {
  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-2 px-4 py-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Building2 className="h-4 w-4" />
        </div>
        <div className="flex flex-col leading-none">
          <span className="text-sm font-semibold tracking-tight">permit-pulse</span>
          <span className="text-[10px] uppercase tracking-widest text-muted-foreground">Houston</span>
        </div>
      </div>

      <nav className="flex-1 px-2">
        <div className="px-2 pb-1 pt-3 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
          Workspace
        </div>
        {NAV.map(({ to, icon: Icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "group mb-0.5 flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
                isActive
                  ? "bg-surface-raised text-foreground"
                  : "text-muted-foreground hover:bg-surface-raised/60 hover:text-foreground"
              )
            }
          >
            <Icon className="h-3.5 w-3.5" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border p-2">
        <button className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm text-muted-foreground hover:bg-surface-raised/60 hover:text-foreground">
          <Settings className="h-3.5 w-3.5" />
          <span>Settings</span>
        </button>
      </div>
    </aside>
  );
}
