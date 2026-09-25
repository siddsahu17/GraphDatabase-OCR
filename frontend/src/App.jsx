import React, { useEffect, useState } from 'react';
import Navbar from './components/Navbar';
import DocumentUploadTab from './components/DocumentUploadTab';
import BatchIngestTab from './components/BatchIngestTab';
import GraphExplorerTab from './components/GraphExplorerTab';
import SchemaRegistryTab from './components/SchemaRegistryTab';
import './index.css';

export default function App() {
  const [activeTab, setActiveTab] = useState('upload');
  const [dbStatus, setDbStatus] = useState('warning');

  useEffect(() => {
    fetch('/api/graph-data')
      .then((res) => res.json())
      .then((data) => {
        if (data.database_connected) {
          setDbStatus('online');
        } else {
          setDbStatus('warning');
        }
      })
      .catch(() => setDbStatus('offline'));
  }, []);

  return (
    <div className="app-container">
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} dbStatus={dbStatus} />

      <main className="main-content">
        {activeTab === 'upload' && <DocumentUploadTab />}
        {activeTab === 'batch' && <BatchIngestTab />}
        {activeTab === 'explorer' && <GraphExplorerTab />}
        {activeTab === 'schema' && <SchemaRegistryTab />}
      </main>
    </div>
  );
}
