import { createRoute } from "@tanstack/react-router";
import { Route as dashboardRoute } from "./_dashboard";
import { useState, useEffect } from "react";
import { apiFetch } from "../lib/api";
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

interface EvalScorePoint {
  date: string;
  faithfulness: number;
  hallucination: number;
  relevancy: number;
}

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: "/eval",
  component: EvalDashboard,
});

function EvalDashboard() {
  const [data, setData] = useState<EvalScorePoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/api/eval/scores?days=30")
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
    return <div className="p-6 text-muted-foreground">Loading evaluation data...</div>;
  }

  if (error) {
    return <div className="p-6 text-red-500">Failed to load evaluation data: {error}</div>;
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">RAG Evaluation Dashboard</h1>
      {data.length === 0 ? (
        <p className="text-muted-foreground">No evaluation data available yet. Run an evaluation to populate scores.</p>
      ) : (
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis domain={[0, 1]} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="faithfulness" stroke="#8884d8" />
            <Line type="monotone" dataKey="hallucination" stroke="#82ca9d" />
            <Line type="monotone" dataKey="relevancy" stroke="#ffc658" />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
