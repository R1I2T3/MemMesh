import ForceGraph2D from "react-force-graph-2d";

interface GraphNode {
  id: string;
  name: string;
  type: string;
  score: number;
}

interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

interface KnowledgeGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (node: GraphNode) => void;
}

export function KnowledgeGraph({
  nodes,
  edges,
  onNodeClick,
}: KnowledgeGraphProps) {
  const graphData = {
    nodes: nodes.map((n) => ({ ...n, val: n.score })),
    links: edges.map((e) => ({
      source: e.source,
      target: e.target,
      label: e.type,
    })),
  };

  return (
    <ForceGraph2D
      graphData={graphData}
      nodeLabel="name"
      nodeColor={(n: any) =>
        n.type === "Person"
          ? "#8884d8"
          : n.type === "Organization"
            ? "#82ca9d"
            : "#ffc658"
      }
      linkLabel="label"
      linkDirectionalArrowLength={6}
      linkDirectionalParticles={2}
      onNodeClick={(node: any) => onNodeClick?.(node)}
    />
  );
}
