import { createRoute } from "@tanstack/react-router";
import { Route as dashboardRoute } from "./_dashboard";
import { useState, useEffect } from "react";
import { apiFetch } from "../lib/api";
import { BarChart3Icon, ActivityIcon, TimerIcon, UsersIcon, ThumbsUpIcon, Loader2Icon } from "lucide-react";

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

const statCards = [
  { key: 'queries_last_hour', label: 'Queries (last hour)', icon: ActivityIcon, color: 'text-indigo-500', bg: 'bg-indigo-500/10' },
  { key: 'queries_last_day', label: 'Queries (last 24h)', icon: BarChart3Icon, color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
  { key: 'avg_latency_ms', label: 'Avg Latency', icon: TimerIcon, color: 'text-amber-500', bg: 'bg-amber-500/10', suffix: 'ms' },
  { key: 'unique_users_last_day', label: 'Unique Users (24h)', icon: UsersIcon, color: 'text-purple-500', bg: 'bg-purple-500/10' },
  { key: 'positive_feedback', label: 'Positive Feedback', icon: ThumbsUpIcon, color: 'text-emerald-500', bg: 'bg-emerald-500/10', isRatio: true },
];

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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground gap-2">
        <Loader2Icon className="size-5 animate-spin" />
        <span className="text-sm">Loading analytics...</span>
      </div>
    );
  }
  if (error) return <div className="p-6 text-destructive text-sm">Failed to load analytics: {error}</div>;
  if (analytics?.message) return <div className="p-6 text-muted-foreground text-sm">{analytics.message}</div>;

  return (
    <div className="p-0 space-y-6">
      <div className="flex flex-col gap-0.5">
        <h1 className="text-xl font-bold tracking-tight">Analytics Dashboard</h1>
        <p className="text-xs text-muted-foreground">System usage and performance metrics</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {statCards.map((card) => {
          const value = analytics?.[card.key as keyof AnalyticsData];
          const Icon = card.icon;
          return (
            <div key={card.key} className="rounded-xl border border-border/60 bg-card p-5 shadow-sm hover:shadow-md transition-shadow duration-200">
              <div className="flex items-start justify-between">
                <div className="flex flex-col gap-1">
                  <span className="text-[11px] font-medium text-muted-foreground">{card.label}</span>
                  <span className="text-2xl font-bold tracking-tight text-foreground">
                    {card.isRatio
                      ? `${analytics?.positive_feedback ?? 0}/${analytics?.total_feedback ?? 0}`
                      : card.suffix
                        ? `${value}${card.suffix}`
                        : value}
                  </span>
                </div>
                <div className={`${card.bg} ${card.color} p-2.5 rounded-xl`}>
                  <Icon className="size-5" />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
