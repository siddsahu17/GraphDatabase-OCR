import React, { useEffect, useState } from 'react';
import { Sliders } from 'lucide-react';

export default function SchemaRegistryTab() {
  const [schemas, setSchemas] = useState({});

  useEffect(() => {
    fetch('/api/schemas')
      .then((res) => res.json())
      .then((data) => setSchemas(data))
      .catch((err) => console.error('Failed to load schemas:', err));
  }, []);

  return (
    <div className="card">
      <div className="card-header">
        <h2><Sliders size={20} /> Dynamic Schema Templates Configuration</h2>
        <p>Customize node properties and edge relationships without modifying backend code.</p>
      </div>

      <div className="mt-4" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '1rem' }}>
        {Object.entries(schemas).map(([key, schema]) => (
          <div key={key} className="card" style={{ background: 'rgba(10, 13, 20, 0.6)' }}>
            <h3>{schema.domain_name || key}</h3>
            <p style={{ color: '#9ca3af', fontSize: '0.85rem', marginBottom: '0.75rem' }}>{schema.description}</p>
            <pre className="code-block">{JSON.stringify(schema, null, 2)}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}
