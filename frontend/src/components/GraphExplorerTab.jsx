import React, { useEffect, useRef, useState } from 'react';
import { Network, RefreshCw, Maximize2, MousePointer, Filter } from 'lucide-react';
import { Network as VisNetwork, DataSet } from 'vis-network/standalone';

export default function GraphExplorerTab() {
  const containerRef = useRef(null);
  const [selectedDomainFilter, setSelectedDomainFilter] = useState('all');
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [selectedNode, setSelectedNode] = useState(null);
  const networkRef = useRef(null);

  const fetchGraphData = async (domain = selectedDomainFilter) => {
    try {
      const url = domain && domain !== 'all' ? `/api/graph-data?domain=${domain}` : '/api/graph-data?domain=all';
      const res = await fetch(url);
      const data = await res.json();
      setGraphData(data);
      renderNetwork(data.nodes || [], data.edges || []);
    } catch (err) {
      console.error('Failed to load graph data:', err);
    }
  };

  useEffect(() => {
    fetchGraphData(selectedDomainFilter);
  }, [selectedDomainFilter]);

  const getNodeColor = (label, graphName) => {
    switch (label) {
      case 'Invoice': return '#6366f1';
      case 'Vendor': return '#10b981';
      case 'Customer': return '#f59e0b';
      case 'MedicalBill': return '#ec4899';
      case 'Patient': return '#3b82f6';
      case 'Hospital': return '#8b5cf6';
      case 'Condition': return '#14b8a6';
      case 'Medication': return '#eab308';
      case 'Document': return '#64748b';
      case 'Page': return '#94a3b8';
      case 'Chunk': return '#475569';
      default: return graphName === 'invoice_graph' ? '#6366f1' : '#ec4899';
    }
  };

  const renderNetwork = (nodes, edges) => {
    if (!containerRef.current) return;

    const visNodes = nodes.map((n) => ({
      id: n.id,
      label: `${n.label}\n${n.properties?.name || n.properties?.invoice_no || n.properties?.bill_id || n.properties?.id || n.id}`,
      color: {
        background: getNodeColor(n.label, n.graph),
        border: '#ffffff',
        highlight: { background: '#d946ef', border: '#ffffff' }
      },
      font: { color: '#ffffff', face: 'Outfit', size: 12 },
      properties: n.properties,
      graph: n.graph,
      shape: 'box',
      margin: 10,
    }));

    const visEdges = edges.map((e) => ({
      from: e.from,
      to: e.to,
      label: e.label,
      arrows: 'to',
      color: { color: 'rgba(99, 102, 241, 0.5)' },
      font: { color: '#a5b4fc', size: 10 },
    }));

    const data = {
      nodes: new DataSet(visNodes),
      edges: new DataSet(visEdges),
    };

    const options = {
      physics: {
        barnesHut: { gravitationalConstant: -3500, springLength: 130 },
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
          <h2><Network size={20} /> Domain Graph Visualization Canvas</h2>
          <span className="badge">{graphData.nodes?.length || 0} Nodes | {graphData.edges?.length || 0} Edges</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <div className="domain-tabs-filter">
            <button
              className={`filter-btn ${selectedDomainFilter === 'all' ? 'active' : ''}`}
              onClick={() => setSelectedDomainFilter('all')}
            >
              🌐 All Domains
            </button>
            <button
              className={`filter-btn ${selectedDomainFilter === 'invoice' ? 'active' : ''}`}
              onClick={() => setSelectedDomainFilter('invoice')}
            >
              📊 Invoice Graph
            </button>
            <button
              className={`filter-btn ${selectedDomainFilter === 'medical' ? 'active' : ''}`}
              onClick={() => setSelectedDomainFilter('medical')}
            >
              🏥 Medical Graph
            </button>
          </div>

          <button className="btn btn-secondary" onClick={() => fetchGraphData(selectedDomainFilter)}>
            <RefreshCw size={16} /> Refresh
          </button>
          <button className="btn btn-secondary" onClick={() => networkRef.current?.fit()}>
            <Maximize2 size={16} /> Recenter
          </button>
        </div>
      </div>

      <div className="canvas-grid">
        <div className="card canvas-card">
          <div ref={containerRef} className="vis-canvas" style={{ width: '100%', height: '100%' }} />
        </div>

        <div className="card inspector-card">
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Node Inspector</h3>
          <div style={{ marginTop: '1rem' }}>
            {selectedNode ? (
              <div>
                <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.4rem' }}>
                  <span className="node-label">{selectedNode.label}</span>
                  {selectedNode.graph && <span className="badge">{selectedNode.graph}</span>}
                </div>
                <h4 style={{ fontSize: '0.9rem', wordBreak: 'break-all', marginBottom: '0.75rem' }}>{selectedNode.id}</h4>
                <table style={{ width: '100%', fontSize: '0.82rem' }}>
                  <tbody>
                    {Object.entries(selectedNode.properties || {}).map(([k, v]) => (
                      <tr key={k} style={{ borderBottom: '1px solid var(--border-color)' }}>
                        <td style={{ padding: '0.4rem 0', color: 'var(--text-secondary)', fontWeight: '600' }}>{k}</td>
                        <td style={{ padding: '0.4rem 0', wordBreak: 'break-all' }}>{String(v)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">
                <MousePointer size={28} />
                <p>Click any node on the graph canvas to inspect its properties and graph origin.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
