import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

// Data refreshes once a day via cron — no need to re-fetch every minute.
// 10-min staleTime drops API load by ~10× on a single client session
// (clicking around, opening multiple pages, etc.) without making the
// dashboard feel stale.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10 * 60_000,
      gcTime: 30 * 60_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      retry: 2,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 5000),
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
