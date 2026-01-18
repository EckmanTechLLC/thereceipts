import { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  ConnectionLineType,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import './GraphPage.css';
import { api } from '../services/api';
import type { GraphNode, GraphEdge, GraphNodeType } from '../types';

/**
 * Color mapping for different node types
 */
const NODE_COLORS: Record<GraphNodeType, string> = {
  blog: '#8b5cf6', // purple
  claim: '#3b82f6', // blue
  source: '#10b981', // green
};

/**
 * Convert backend graph nodes to ReactFlow nodes with grid layout
 */
function convertToReactFlowNodes(graphNodes: GraphNode[]): Node[] {
  // Group nodes by type
  const blogNodes = graphNodes.filter(n => n.type === 'blog');
  const claimNodes = graphNodes.filter(n => n.type === 'claim');
  const sourceNodes = graphNodes.filter(n => n.type === 'source');

  const nodes: Node[] = [];
  const horizontalSpacing = 280;
  const verticalSpacing = 150;
  const nodesPerRow = 6; // Max nodes per row for grid layout

  const createNodeStyle = (type: GraphNodeType) => ({
    background: NODE_COLORS[type],
    color: '#ffffff',
    border: '2px solid #1f2937',
    borderRadius: '8px',
    padding: '10px',
    fontSize: '12px',
    fontWeight: 'bold',
    width: 200,
  });

  // Position blog nodes at the top in a grid
  blogNodes.forEach((node, index) => {
    const row = Math.floor(index / nodesPerRow);
    const col = index % nodesPerRow;
    nodes.push({
      id: node.id,
      type: 'default',
      position: {
        x: col * horizontalSpacing,
        y: row * verticalSpacing,
      },
      data: { label: node.label, ...node },
      style: createNodeStyle(node.type),
    });
  });

  // Calculate starting Y position for claims (after blogs)
  const blogRows = Math.ceil(blogNodes.length / nodesPerRow);
  const claimStartY = blogRows * verticalSpacing + 250; // Extra gap between layers

  // Position claim nodes in the middle in a grid
  claimNodes.forEach((node, index) => {
    const row = Math.floor(index / nodesPerRow);
    const col = index % nodesPerRow;
    nodes.push({
      id: node.id,
      type: 'default',
      position: {
        x: col * horizontalSpacing,
        y: claimStartY + row * verticalSpacing,
      },
      data: { label: node.label, ...node },
      style: createNodeStyle(node.type),
    });
  });

  // Calculate starting Y position for sources (after claims)
  const claimRows = Math.ceil(claimNodes.length / nodesPerRow);
  const sourceStartY = claimStartY + claimRows * verticalSpacing + 250; // Extra gap between layers

  // Position source nodes at the bottom in a grid
  sourceNodes.forEach((node, index) => {
    const row = Math.floor(index / nodesPerRow);
    const col = index % nodesPerRow;
    nodes.push({
      id: node.id,
      type: 'default',
      position: {
        x: col * horizontalSpacing,
        y: sourceStartY + row * verticalSpacing,
      },
      data: { label: node.label, ...node },
      style: createNodeStyle(node.type),
    });
  });

  return nodes;
}

/**
 * Convert backend graph edges to ReactFlow edges
 */
function convertToReactFlowEdges(graphEdges: GraphEdge[]): Edge[] {
  return graphEdges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: 'smoothstep',
    label: edge.type,
    labelStyle: {
      fontSize: '10px',
      fill: '#6b7280',
    },
    style: {
      stroke: '#9ca3af',
      strokeWidth: 2,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#9ca3af',
    },
    data: edge,
  }));
}

/**
 * GraphPage - Knowledge graph visualization showing blogs → claims → sources
 */
export function GraphPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>(null);

  // Load graph data
  useEffect(() => {
    async function loadGraph() {
      try {
        setLoading(true);
        setError(null);
        const data = await api.getGraph();
        setGraphData(data);
      } catch (err) {
        console.error('Failed to load graph:', err);
        setError('Failed to load knowledge graph. Please try again later.');
      } finally {
        setLoading(false);
      }
    }

    loadGraph();
  }, []);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Convert and set nodes/edges when graphData changes
  useEffect(() => {
    if (graphData) {
      const newNodes = convertToReactFlowNodes(graphData.nodes);
      const newEdges = convertToReactFlowEdges(graphData.edges);
      setNodes(newNodes);
      setEdges(newEdges);
    }
  }, [graphData, setNodes, setEdges]);

  // Handle node click - navigate to appropriate page
  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      const graphNode = node.data as GraphNode;

      if (graphNode.type === 'blog') {
        const blogId = graphNode.id.replace('blog-', '');
        navigate(`/read/${blogId}`);
      } else if (graphNode.type === 'claim') {
        const claimId = graphNode.id.replace('claim-', '');
        navigate(`/audits/${claimId}`);
      }
      // Sources don't have detail pages yet
    },
    [navigate]
  );

  if (loading) {
    return (
      <div className="graph-page">
        <div className="graph-loading">Loading knowledge graph...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="graph-page">
        <div className="graph-error">{error}</div>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="graph-page">
        <div className="graph-empty">
          <h2>No Graph Data</h2>
          <p>The knowledge graph is empty. Generate some blog posts to see relationships.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="graph-page">
      <div className="graph-header">
        <h1>Knowledge Graph</h1>
        <p>Explore relationships between blogs, claims, and sources. Click nodes to view details.</p>
        <div className="graph-legend">
          <div className="legend-item">
            <span className="legend-color" style={{ backgroundColor: NODE_COLORS.blog }}></span>
            <span>Blog Posts</span>
          </div>
          <div className="legend-item">
            <span className="legend-color" style={{ backgroundColor: NODE_COLORS.claim }}></span>
            <span>Claims</span>
          </div>
          <div className="legend-item">
            <span className="legend-color" style={{ backgroundColor: NODE_COLORS.source }}></span>
            <span>Sources</span>
          </div>
        </div>
      </div>

      <div className="graph-container">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          connectionLineType={ConnectionLineType.SmoothStep}
          fitView
          attributionPosition="bottom-left"
        >
          <Background />
          <Controls />
          <MiniMap
            nodeColor={(node) => {
              const graphNode = node.data as GraphNode;
              return NODE_COLORS[graphNode.type] || '#6b7280';
            }}
            maskColor="rgba(0, 0, 0, 0.2)"
          />
        </ReactFlow>
      </div>
    </div>
  );
}
