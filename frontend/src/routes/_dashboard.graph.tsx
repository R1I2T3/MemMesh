import { createRoute } from "@tanstack/react-router";
import { Route as dashboardRoute } from "./_dashboard";
import { useState, useEffect } from "react";
import { apiFetch } from "../lib/api";
import { KnowledgeGraph } from "../components/knowledge-graph";
import { EntityDetailPanel } from "../components/entity-detail-panel";

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: "/graph",
  component: GraphExplorer,
});

function GraphExplorer() {
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<any>(null);
  const teamId = localStorage.getItem("active_team_id");

  useEffect(() => {
    if (!teamId) return;
    apiFetch(`/api/team/${teamId}/graph/explore?limit=100`, {
      headers: { 'X-Active-Team-ID': teamId } as Record<string, string>,
    })
      .then((r) => r.json())
      .then((data) => {
        setNodes(data.nodes || []);
        setEdges(data.edges || []);
      });
  }, [teamId]);

  return (
    <div className="flex gap-4 p-4">
      <div className="flex-1">
        <KnowledgeGraph
          nodes={nodes}
          edges={edges}
          onNodeClick={setSelectedEntity}
        />
      </div>
      {selectedEntity && (
        <div className="w-80">
          <EntityDetailPanel entity={selectedEntity} />
        </div>
      )}
    </div>
  );
}
