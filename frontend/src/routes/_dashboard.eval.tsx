import { createRoute } from "@tanstack/react-router";
import { Route as dashboardRoute } from "./_dashboard";
import { useState, useEffect } from "react";
import { apiFetch } from "../lib/api";
import { evalSearchSchema } from "./search.schemas";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { BarChart3Icon, Loader2Icon } from "lucide-react";

interface EvalScorePoint {
  date: string;
  faithfulness: number;
  hallucination: number;
  relevancy: number;
}

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: "/eval",
  validateSearch: evalSearchSchema,
  component: EvalDashboard,
});

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card/95 backdrop-blur-md border border-border/60 rounded-xl shadow-sm px-3 py-2 text-xs">
      <p className="font-semibold text-foreground mb-1">{label}</p>
      {payload.map((entry: any) => (
        <div key={entry.name} className="flex items-center gap-2 text-muted-foreground">
          <span className="size-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="capitalize">{entry.name}:</span>
          <span className="font-mono font-medium text-foreground">{(entry.value * 100).toFixed(0)}%</span>
        </div>
      ))}
    </div>
  );
};

function EvalDashboard() {
  const { days } = Route.useSearch();
  const [data, setData] = useState<EvalScorePoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch(`/api/eval/scores?days=${days}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
        return r.json();
      })
      .then((d) => {
        setData(d.scores || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground gap-2">
        <Loader2Icon className="size-5 animate-spin" />
        <span className="text-sm">Loading evaluation data...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-48 text-destructive gap-2">
        <span className="text-sm">Failed to load evaluation data: {error}</span>
      </div>
    );
  }

  return (
    <div className="p-0 space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center rounded-xl bg-indigo-500/10 p-2.5 text-indigo-600 dark:text-indigo-400">
          <BarChart3Icon className="size-5" />
        </div>
        <div className="flex flex-col gap-0.5">
          <h1 className="text-xl font-bold tracking-tight">RAG Evaluation Dashboard</h1>
          <p className="text-xs text-muted-foreground">Track faithfulness, hallucination, and relevancy over time</p>
        </div>
      </div>
      {data.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-12 text-center text-muted-foreground gap-2 border border-dashed border-border/60 rounded-xl">
          <BarChart3Icon className="size-8 opacity-30" />
          <p className="text-sm">No evaluation data available yet.</p>
          <p className="text-xs">Run an evaluation in the Docs Console to populate scores.</p>
        </div>
      ) : (
        <div className="border border-border/60 rounded-xl bg-card p-4 shadow-sm">
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" strokeOpacity={0.5} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                axisLine={{ stroke: 'var(--border)', strokeOpacity: 0.5 }}
                tickLine={false}
              />
              <YAxis
                domain={[0, 1]}
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: '12px', paddingTop: '8px' }}
              />
              <Line
                type="monotone"
                dataKey="faithfulness"
                stroke="var(--primary)"
                strokeWidth={2}
                dot={{ r: 3, fill: 'var(--primary)' }}
                activeDot={{ r: 5 }}
              />
              <Line
                type="monotone"
                dataKey="hallucination"
                stroke="#82ca9d"
                strokeWidth={2}
                dot={{ r: 3, fill: '#82ca9d' }}
                activeDot={{ r: 5 }}
              />
              <Line
                type="monotone"
                dataKey="relevancy"
                stroke="#ffc658"
                strokeWidth={2}
                dot={{ r: 3, fill: '#ffc658' }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
