import React from 'react';
import { Network, Upload, Layers, Sliders, Database } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab, dbStatus }) {
  return (
    <header className="navbar">
      <div className="brand">
        <div className="brand-logo">
          <Network size={24} />
        </div>
        <div className="brand-title">
          <h1>FalkorDB Graph OCR</h1>
          <span className="badge">React + Vite + Docling</span>
        </div>
      </div>

      <nav className="nav-links">
        <button
          className={`nav-btn ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          <Upload size={16} /> Document Upload
        </button>
        <button
          className={`nav-btn ${activeTab === 'batch' ? 'active' : ''}`}
          onClick={() => setActiveTab('batch')}
        >
          <Layers size={16} /> Batch Dataset Ingest
        </button>
        <button
          className={`nav-btn ${activeTab === 'explorer' ? 'active' : ''}`}
          onClick={() => setActiveTab('explorer')}
        >
          <Network size={16} /> Graph Explorer
        </button>
        <button
          className={`nav-btn ${activeTab === 'schema' ? 'active' : ''}`}
          onClick={() => setActiveTab('schema')}
        >
          <Sliders size={16} /> Schema Registry
        </button>
      </nav>

      <div className="db-status">
        <span className={`status-dot ${dbStatus}`} />
        <span>
          {dbStatus === 'online' ? 'FalkorDB Online' : dbStatus === 'warning' ? 'Mock Mode' : 'FalkorDB Offline'}
        </span>
      </div>
    </header>
  );
}
