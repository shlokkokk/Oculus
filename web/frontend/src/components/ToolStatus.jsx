import { useState, useEffect } from 'react';
import { Wrench, RefreshCw } from 'lucide-react';
import { api } from '../api/client';

export default function ToolStatus() {
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadTools = (force = false) => {
    setLoading(true);
    api.getTools(force)
      .then(r => setTools(r.tools || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => loadTools(), []);

  const installed = tools.filter(t => t.installed).length;
  const total = tools.length;

  return (
    <div>
      <div className="page-header">
        <h2>Tool Status</h2>
        <p>Oculus relies on external security tools. Check their installation status below.</p>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
        <div className="stat-card" style={{ display: 'inline-flex', gap: 12, alignItems: 'center', padding: '12px 20px', textAlign: 'left' }}>
          <Wrench size={20} style={{ color: 'var(--accent)' }} />
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: installed === total ? 'var(--accent-green)' : 'var(--accent-amber)' }}>
              {installed}/{total}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>Tools Available</div>
          </div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={() => loadTools(true)} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spinning' : ''} /> Refresh
        </button>
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><div className="spinner" /></div>
      ) : (
        <div className="tool-grid">
          {tools.map(tool => (
            <div key={tool.name} className="tool-item">
              <div className={`tool-status-dot ${tool.installed ? 'installed' : 'missing'}`} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="tool-name">{tool.name}</div>
                {tool.installed && tool.path && <div className="tool-path">{tool.path}</div>}
                {!tool.installed && tool.install_command && (
                  <div className="tool-path" style={{ color: 'var(--accent-amber)' }}>{tool.install_command}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
