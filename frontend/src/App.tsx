import { Routes, Route } from "react-router-dom";
import { AppShell } from "@/components/shell/AppShell";
import { CommandCenter } from "@/pages/CommandCenter";
import { MapPage } from "@/pages/MapPage";
import { BuildersPage } from "@/pages/BuildersPage";
import { SubmarketsPage } from "@/pages/SubmarketsPage";
import { OpportunitiesPage } from "@/pages/OpportunitiesPage";
import { PermitsPage } from "@/pages/PermitsPage";
import { DailyReportPage } from "@/pages/DailyReportPage";
import { WatchlistPage } from "@/pages/WatchlistPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<CommandCenter />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/builders" element={<BuildersPage />} />
        <Route path="/submarkets" element={<SubmarketsPage />} />
        <Route path="/opportunities" element={<OpportunitiesPage />} />
        <Route path="/permits" element={<PermitsPage />} />
        <Route path="/daily-report" element={<DailyReportPage />} />
        <Route path="/watchlist" element={<WatchlistPage />} />
      </Route>
    </Routes>
  );
}
