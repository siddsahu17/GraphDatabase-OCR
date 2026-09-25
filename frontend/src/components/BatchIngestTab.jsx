import React, { useState } from 'react';
import { Layers, Play } from 'lucide-react';

export default function BatchIngestTab() {
  const [category, setCategory] = useState('Invoice');
  const [maxCount, setMaxCount] = useState(5);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState('');
  const [batchResults, setBatchResults] = useState(null);

  const startBatch = async () => {
    setRunning(true);
    setProgress(30);
    setStatusText(`Processing batch of ${maxCount} files from data/${category}...`);

    try {
      const res = await fetch('/api/batch-ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category, max_count: maxCount }),
      });

      const data = await res.json();
      setProgress(100);
      setStatusText(`Completed batch! Ingested ${data.total_nodes_ingested} nodes and ${data.total_relationships_ingested} relationships.`);
      setBatchResults(data);
    } catch (err) {
      setStatusText(`Batch Error: ${err.message}`);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <h2><Layers size={20} /> Batch Dataset Processing (`data/` Directory)</h2>
        <p>Process multiple document images automatically from your local dataset folders.</p>
      </div>

      <div className="batch-controls-grid">
        <div className="form-group">
          <label>Dataset Category Subfolder</label>
          <select
            className="custom-select"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="Invoice">Invoice Dataset (data/Invoice/ - ~1000+ files)</option>
            <option value="Medical/bills">Medical Bills Dataset (data/Medical/bills/ - 500 files)</option>
            <option value="Medical/discharge_summaries">Medical Discharge Summaries (data/Medical/discharge_summaries/ - 500 files)</option>
          </select>
        </div>

        <div className="form-group">
          <label>Number of Images to Process</label>
          <input
            type="number"
            className="custom-input"
            value={maxCount}
            min="1"
            max="50"
            onChange={(e) => setMaxCount(parseInt(e.target.value) || 1)}
          />
        </div>

        <div className="form-group align-end">
          <button
            className="btn btn-primary"
            disabled={running}
            onClick={startBatch}
          >
            <Play size={16} /> Start Batch Pipeline
          </button>
        </div>
      </div>

      {running || progress > 0 ? (
        <div className="mt-4">
          <div className="progress-bar-container">
            <div className="progress-bar" style={{ width: `${progress}%` }} />
          </div>
          <div className="progress-labels">
            <span>{statusText}</span>
            <span>{progress}%</span>
          </div>
        </div>
      ) : null}

      <div className="mt-4">
        <h3>Batch Results Summary</h3>
        {batchResults ? (
          <div className="mt-2" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', textIndent: '0', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#9ca3af', textAlign: 'left' }}>
                  <th style={{ padding: '0.5rem' }}>File Name</th>
                  <th>Status</th>
                  <th>Nodes Created</th>
                  <th>Edges Created</th>
                </tr>
              </thead>
              <tbody>
                {(batchResults.details || []).map((item, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '0.5rem', fontFamily: 'monospace' }}>{item.filename}</td>
                    <td><span style={{ color: item.status === 'success' ? '#10b981' : '#ef4444' }}>{item.status}</span></td>
                    <td>{item.nodes || 0}</td>
                    <td>{item.relationships || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-muted mt-2">No batch execution started yet. Click "Start Batch Pipeline" above.</p>
        )}
      </div>
    </div>
  );
}
