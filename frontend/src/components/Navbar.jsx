import React from 'react';
import { Network, Upload, Layers, Sliders, Sun, Moon } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab, dbStatus, theme, setTheme }) {
  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  return (
    <header className="navbar">
      <div className="brand">
        <div className="brand-logo">
          <Network size={24} />
        </div>
        <div className="brand-title">
          <h1>BodhiECG Graph OCR</h1>
          <span className="badge">Multi-Domain FalkorDB</span>
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
          <Layers size={16} /> Batch Datasets
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

      <div className="right-controls">
        <button
          className="theme-toggle-btn"
          onClick={toggleTheme}
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
        >
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        <div className="db-status">
          <span className={`status-dot ${dbStatus}`} />
          <span>
            {dbStatus === 'online' ? 'FalkorDB Online' : dbStatus === 'warning' ? 'Mock Mode' : 'FalkorDB Offline'}
          </span>
        </div>
      </div>
    </header>
  );
}
