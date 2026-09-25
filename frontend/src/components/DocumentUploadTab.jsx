import React, { useState } from 'react';
import { Upload, FileImage, X, Zap, Database, Wand2, Plus } from 'lucide-react';

export default function DocumentUploadTab() {
  const [selectedDomain, setSelectedDomain] = useState('invoice');
  const [files, setFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);
  const [activeSubTab, setActiveSubTab] = useState('nodes');
  const [result, setResult] = useState(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const newFiles = Array.from(e.dataTransfer.files);
      setFiles((prev) => [...prev, ...newFiles]);
      setCurrentStep(1);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files);
      setFiles((prev) => [...prev, ...newFiles]);
      setCurrentStep(1);
    }
  };

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    if (files.length <= 1) {
      setResult(null);
      setCurrentStep(1);
    }
  };

  const runProcessing = async () => {
    if (files.length === 0) return;

    setProcessing(true);
    setCurrentStep(2);

    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });
    formData.append('domain', selectedDomain);

    try {
      setCurrentStep(3);
      const res = await fetch('/api/process-images', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Processing failed.');
      }

      const data = await res.json();
      setResult(data);
      setCurrentStep(4);
    } catch (err) {
      alert(`Error: ${err.message}`);
      setCurrentStep(1);
    } finally {
      setProcessing(false);
    }
  };

  const commitGraph = async () => {
    if (!result || !result.graph) return;

    setIngesting(true);
    try {
      const res = await fetch('/api/ingest-graph', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ graph: result.graph }),
      });

      const data = await res.json();
      alert(`Successfully committed ${data.nodes_ingested} nodes and ${data.relationships_ingested} relationships into FalkorDB!`);
    } catch (err) {
      alert(`Commit error: ${err.message}`);
    } finally {
      setIngesting(false);
    }
  };

  const nodes = result?.graph?.nodes || [];
  const rels = result?.graph?.relationships || [];

  return (
    <div className="grid-2col">
      {/* Left Column: Input */}
      <div className="card">
        <div className="card-header">
          <h2><Upload size={20} /> Upload Multiple Document Images</h2>
          <p>Upload single or multiple Invoice / Medical scans to run Docling OCR & extract FalkorDB graph nodes.</p>
        </div>

        <div className="form-group">
          <label>Target Knowledge Domain Schema</label>
          <select
            className="custom-select"
            value={selectedDomain}
            onChange={(e) => setSelectedDomain(e.target.value)}
          >
            <option value="invoice">Commercial Invoice (Vendor, Invoice, Customer, LineItem)</option>
            <option value="medical_bill">Medical Bill (Hospital, Patient, Bill, BillingItem)</option>
            <option value="discharge_summary">Medical Discharge Summary (Patient, Condition, Medication)</option>
          </select>
        </div>

        <div
          className={`drop-zone ${dragOver ? 'dragover' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => document.getElementById('file-input-multi').click()}
        >
          <FileImage className="drop-icon" />
          <p className="drop-title">Drag & drop document scan(s) here</p>
          <span className="drop-sub">Supports multiple JPG, PNG, WEBP files</span>
          <input
            type="file"
            id="file-input-multi"
            accept="image/*"
            multiple
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
          <button type="button" className="btn btn-secondary"><Plus size={16} /> Browse Files</button>
        </div>

        {files.length > 0 && (
          <div className="mt-4" style={{ maxHeight: '180px', overflowY: 'auto' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#9ca3af', marginBottom: '0.5rem' }}>
              Selected Files ({files.length})
            </div>
            {files.map((f, idx) => (
              <div key={idx} className="file-preview-card" style={{ marginTop: '0.4rem' }}>
                <div className="file-info">
                  <FileImage size={20} color="#6366f1" />
                  <div>
                    <div className="file-name">{f.name}</div>
                    <div className="file-size">{(f.size / 1024).toFixed(1)} KB</div>
                  </div>
                </div>
                <button className="icon-btn danger" onClick={(e) => { e.stopPropagation(); removeFile(idx); }}>
                  <X size={16} />
                </button>
              </div>
            ))}
          </div>
        )}

        <button
          className="btn btn-primary btn-full mt-4"
          disabled={files.length === 0 || processing}
          onClick={runProcessing}
        >
          {processing ? <Zap className="fa-spin" size={18} /> : <Zap size={18} />}
          {processing ? `Processing ${files.length} Document(s)...` : `Run Docling OCR & Extract Graph (${files.length} Files)`}
        </button>
      </div>

      {/* Right Column: Results & Stepper */}
      <div className="card">
        <div className="card-header">
          <h2>Extraction Pipeline Status</h2>
        </div>

        {/* Stepper */}
        <div className="stepper">
          {[
            { num: 1, label: 'Upload' },
            { num: 2, label: 'Docling OCR' },
            { num: 3, label: 'LLM Extraction' },
            { num: 4, label: 'FalkorDB Graph' },
          ].map((s, idx) => (
            <React.Fragment key={s.num}>
              <div className={`step-item ${currentStep > s.num ? 'completed' : currentStep === s.num ? 'active' : ''}`}>
                <div className="step-badge">{s.num}</div>
                <div className="step-label">{s.label}</div>
              </div>
              {idx < 3 && <div className="step-line" />}
            </React.Fragment>
          ))}
        </div>

        {/* Results Subtabs */}
        <div className="sub-tabs-header">
          <button
            className={`sub-tab-btn ${activeSubTab === 'nodes' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('nodes')}
          >
            Extracted Graph ({nodes.length} Nodes, {rels.length} Edges)
          </button>
          <button
            className={`sub-tab-btn ${activeSubTab === 'ocr' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('ocr')}
          >
            Docling OCR Text
          </button>
          <button
            className={`sub-tab-btn ${activeSubTab === 'json' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('json')}
          >
            Raw JSON
          </button>
        </div>

        <div className="sub-tab-content">
          {activeSubTab === 'nodes' && (
            <div className="nodes-grid">
              {nodes.length > 0 ? (
                nodes.map((n, i) => (
                  <div key={i} className="node-card">
                    <div className="node-card-header">
                      <span className="node-label">{n.label}</span>
                      <span className="node-id">#{n.id}</span>
                    </div>
                    <div className="node-props">
                      {Object.entries(n.properties || {}).map(([k, v]) => (
                        <div key={k}><strong>{k}:</strong> {v}</div>
                      ))}
                    </div>
                  </div>
                ))
              ) : (
                <div className="empty-state">
                  <Wand2 size={32} />
                  <p>Upload document image(s) and click "Run Docling OCR" to extract graph entities.</p>
                </div>
              )}
            </div>
          )}

          {activeSubTab === 'ocr' && (
            <pre className="code-block">{result?.parsed_text || 'Docling text will appear here...'}</pre>
          )}

          {activeSubTab === 'json' && (
            <pre className="code-block">{result ? JSON.stringify(result, null, 2) : '{}'}</pre>
          )}
        </div>

        <button
          className="btn btn-success btn-full mt-4"
          disabled={!result || ingesting}
          onClick={commitGraph}
        >
          <Database size={18} />
          {ingesting ? 'Committing to FalkorDB...' : 'Commit Combined Graph into FalkorDB'}
        </button>
      </div>
    </div>
  );
}
