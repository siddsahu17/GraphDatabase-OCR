import React, { useEffect, useRef, useState } from 'react';
import { Network, RefreshCw, Maximize2, MousePointer } from 'lucide-react';
import { Network as VisNetwork, DataSet } from 'vis-network/standalone';

export default function GraphExplorerTab() {
  const containerRef = useRef(null);
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [selectedNode, setSelectedNode] = useState(null);
  const networkRef = useRef(null);

  const fetchGraphData = async () => {
    try {
      const res = await fetch('/api/graph-data');
      const data = await res.json();
      setGraphData(data);
      renderNetwork(data.nodes || [], data.edges || []);
    } catch (err) {
      console.error('Failed to load graph data:', err);
    }
  };

  useEffect(() => {
    fetchGraphData();
  }, []);

  const getNodeColor = (label) => {
    switch (label) {
      case 'Invoice': return '#6366f1';
      case 'Vendor': return '#10b981';
      case 'Customer': return '#f59e0b';
      case 'MedicalBill': return '#ec4899';
      case 'Patient': return '#3b82f6';
      case 'Hospital': return '#8b5cf6';
      default: return '#64748b';
    }
  };

  const renderNetwork = (nodes, edges) => {
    if (!containerRef.current) return;

    const visNodes = nodes.map((n) => ({
      id: n.id,
      label: `${n.label}\n${n.properties?.name || n.properties?.invoice_number || n.properties?.bill_id || n.id}`,
      color: getNodeColor(n.label),
      font: { color: '#ffffff', face: 'Outfit' },
      properties: n.properties,
      shape: 'box',
      margin: 10,
    }));

    const visEdges = edges.map((e) => ({
      from: e.from,
      to: e.to,
      label: e.label,
      arrows: 'to',
      color: { color: 'rgba(99, 102, 241, 0.6)' },
      font: { color: '#a5b4fc', size: 10 },
    }));

    const data = {
      nodes: new DataSet(visNodes),
      edges: new DataSet(visEdges),
    };

    const options = {
      physics: {
        barnesHut: { gravitationalConstant: -3000, springLength: 120 },
      },
      interaction: { hover: true },
    };

    networkRef.current = new VisNetwork(containerRef.current, data, options);

    networkRef.current.on('click', (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        const target = visNodes.find((n) => n.id === nodeId);
        if (target) setSelectedNode(target);
      }
    });
  };

  return (
    <div className="explorer-layout">
      <div className="explorer-header card">
        <div>
          <h2><Network size={20} /> FalkorDB Graph Visualization Canvas</h2>
          <span className="badge">{graphData.nodes?.length || 0} Nodes | {graphData.edges?.length || 0} Edges</span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={fetchGraphData}>
            <RefreshCw size={16} /> Refresh Graph
          </button>
          <button className="btn btn-secondary" onClick={() => networkRef.current?.fit()}>
            <Maximize2 size={16} /> Recenter View
          </button>
        </div>
      </div>

      <div className="canvas-grid">
        <div className="card canvas-card">
          <div ref={containerRef} className="vis-canvas" style={{ width: '100%', height: '100%' }} />
        </div>

        <div className="card inspector-card">
          <h3>Node Inspector</h3>
          <div style={{ marginTop: '1rem' }}>
            {selectedNode ? (
              <div>
                <span className="node-label">{selectedNode.label}</span>
                <h4 style={{ marginTop: '0.25rem', marginBottom: '0.75rem' }}>{selectedNode.id}</h4>
                <table style={{ width: '100%', fontSize: '0.85rem', textIndent: '0' }}>
                  <tbody>
                    {Object.entries(selectedNode.properties || {}).map(([k, v]) => (
                      <tr key={k} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '0.4rem', color: '#9ca3af', fontWeight: '600' }}>{k}</td>
                        <td style={{ padding: '0.4rem' }}>{v}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">
                <MousePointer size={28} />
                <p>Click any node on the graph canvas to inspect its properties.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
