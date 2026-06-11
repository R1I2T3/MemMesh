import { useState, useEffect } from "react";
import { apiFetch } from "../lib/api";

interface EntityNode {
  id: string;
  name: string;
  type: string;
  score: number;
}

interface EntityDetailPanelProps {
  entity: EntityNode;
}

export function EntityDetailPanel({ entity }: EntityDetailPanelProps) {
  const [neighbors, setNeighbors] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const teamId = localStorage.getItem("active_team_id");
    if (!teamId) return;
    setLoading(true);
    apiFetch(`/api/team/${teamId}/graph/explore?query=${entity.name}&limit=20`, {
      headers: { 'X-Active-Team-ID': teamId } as Record<string, string>,
    })
      .then((r) => r.json())
      .then((data) => setNeighbors(data.edges || []))
      .catch(() => setNeighbors([]))
      .finally(() => setLoading(false));
  }, [entity]);

  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="font-semibold text-lg">{entity.name}</h3>
      <p className="text-sm text-muted-foreground">Type: {entity.type}</p>
      <p className="text-sm text-muted-foreground">
        Importance: {(entity.score || 0).toFixed(2)}
      </p>
      <div className="mt-4">
        <h4 className="text-sm font-medium mb-2">Relationships</h4>
        {loading && (
          <p className="text-xs text-muted-foreground">Loading relationships...</p>
        )}
        {!loading && neighbors.length === 0 && (
          <p className="text-xs text-muted-foreground">
            No relationships found
          </p>
        )}
        <ul className="space-y-1">
          {neighbors.slice(0, 10).map((e: any, i: number) => (
            <li key={i} className="text-xs text-muted-foreground">
              {e.source} → {e.type} → {e.target}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
