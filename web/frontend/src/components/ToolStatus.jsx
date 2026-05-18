import { useState, useEffect } from 'react';
import { Wrench, RefreshCw } from 'lucide-react';
import { api } from '../api/client';

export default function ToolStatus() {
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [hoveredTool, setHoveredTool] = useState(null);

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
          {tools.map(tool => {
            const isHovered = hoveredTool === tool.name;
            const displayPath = tool.path || tool.install_command || 'No path available';

            return (
              <div 
                key={tool.name} 
                className="tool-item"
                onMouseEnter={() => setHoveredTool(tool.name)}
                onMouseLeave={() => setHoveredTool(null)}
                style={{ position: 'relative' }}
              >
                <div className={`tool-status-dot ${tool.installed ? 'installed' : 'missing'}`} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="tool-name">{tool.name}</div>
                  {tool.installed && tool.path && <div className="tool-path">{tool.path}</div>}
                  {!tool.installed && tool.install_command && (
                    <div className="tool-path" style={{ color: 'var(--accent-amber)' }}>{tool.install_command}</div>
                  )}
                </div>

                {/* Premium Monospace Path Tooltip */}
                {isHovered && (
                  <div style={{
                    position: 'absolute',
                    bottom: 'calc(100% + 6px)',
                    left: 0,
                    background: 'var(--bg-secondary)',
                    border: '1px solid var(--accent)',
                    borderRadius: 6,
                    padding: '8px 12px',
                    fontSize: 10.5,
                    lineHeight: 1.4,
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-primary)',
                    whiteSpace: 'normal',
                    wordBreak: 'break-all',
                    width: '240px',
                    zIndex: 50,
                    boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
                    pointerEvents: 'none',
                  }}>
                    <span style={{ color: 'var(--accent)', fontWeight: 600, display: 'block', marginBottom: 2, fontFamily: 'var(--font-sans)', fontSize: 10 }}>
                      {tool.installed ? 'FULL PATH' : 'INSTALL COMMAND'}
                    </span>
                    {displayPath}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
