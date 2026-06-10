import { createRoute } from "@tanstack/react-router";
import { Route as dashboardRoute } from "./_dashboard";
import { useState, useEffect } from "react";
import { apiFetch } from "../lib/api";

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: "/analytics",
  component: AnalyticsDashboard,
});

interface AnalyticsData {
  queries_last_hour: number;
  queries_last_day: number;
  avg_latency_ms: number;
  unique_users_last_day: number;
  positive_feedback: number;
  total_feedback: number;
  message?: string;
}

function AnalyticsDashboard() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch("/api/admin/analytics", { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
        return r.json();
      })
      .then((d) => {
        setAnalytics(d);
        setLoading(false);
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          setError(err.message);
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, []);

  if (loading) return <div className="p-6 text-muted-foreground">Loading analytics...</div>;
  if (error) return <div className="p-6 text-red-500">Failed to load analytics: {error}</div>;
  if (analytics.message)
    return <div className="p-6 text-muted-foreground">{analytics.message}</div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Analytics Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg border p-4 bg-card">
          <div className="text-sm text-muted-foreground">
            Queries (last hour)
          </div>
          <div className="text-3xl font-bold">{analytics.queries_last_hour}</div>
        </div>
        <div className="rounded-lg border p-4 bg-card">
          <div className="text-sm text-muted-foreground">Queries (last 24h)</div>
          <div className="text-3xl font-bold">{analytics.queries_last_day}</div>
        </div>
        <div className="rounded-lg border p-4 bg-card">
          <div className="text-sm text-muted-foreground">Avg Latency</div>
          <div className="text-3xl font-bold">{analytics.avg_latency_ms}ms</div>
        </div>
        <div className="rounded-lg border p-4 bg-card">
          <div className="text-sm text-muted-foreground">Unique Users (24h)</div>
          <div className="text-3xl font-bold">{analytics.unique_users_last_day}</div>
        </div>
        <div className="rounded-lg border p-4 bg-card">
          <div className="text-sm text-muted-foreground">Positive Feedback</div>
          <div className="text-3xl font-bold">{analytics.positive_feedback}/{analytics.total_feedback}</div>
        </div>
      </div>
    </div>
  );
}
