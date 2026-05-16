import { useState, useEffect } from 'react';
import { FolderOpen, File, FileText, ChevronRight, ChevronDown, Download, Search } from 'lucide-react';
import { api } from '../api/client';

function FileTree({ items, onSelect, selectedPath, depth = 0 }) {
  const [expanded, setExpanded] = useState({});
  const toggle = (path) => setExpanded(prev => ({ ...prev, [path]: !prev[path] }));

  return (
    <div className="file-tree">
      {items.map(item => (
        <div key={item.path}>
          <div
            className={`file-tree-item ${selectedPath === item.path ? 'active' : ''}`}
            style={{ paddingLeft: 8 + depth * 16 }}
            onClick={() => item.is_dir ? toggle(item.path) : onSelect(item)}
          >
            {item.is_dir ? (expanded[item.path] ? <ChevronDown size={14} /> : <ChevronRight size={14} />) : <File size={14} />}
            <span style={{ flex: 1 }}>{item.name}</span>
            {!item.is_dir && <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>{(item.size / 1024).toFixed(1)}K</span>}
          </div>
          {item.is_dir && expanded[item.path] && item.children && (
            <FileTree items={item.children} onSelect={onSelect} selectedPath={selectedPath} depth={depth + 1} />
          )}
        </div>
      ))}
    </div>
  );
}

export default function ResultsViewer({ domain }) {
  const [artifacts, setArtifacts] = useState([]);
  const [selected, setSelected] = useState(null);
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [sessions, setSessions] = useState([]);
  const [activeDomain, setActiveDomain] = useState(domain || '');

  useEffect(() => {
    api.listSessions().then(r => setSessions(r.sessions || [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (!activeDomain) return;
    setLoading(true);
    api.listResults(activeDomain)
      .then(r => { setArtifacts(r.artifacts || []); setError(''); })
      .catch(e => { setArtifacts([]); setError(e.message); })
      .finally(() => setLoading(false));
  }, [activeDomain]);

  const handleSelect = async (item) => {
    setSelected(item);
    setContent(null);
    try {
      const data = await api.getFile(activeDomain, item.path);
      setContent(data);
    } catch (e) {
      setContent({ content: `Error loading file: ${e.message}`, type: 'text', name: item.name });
    }
  };

  if (!activeDomain) {
    return (
      <div>
        <div className="page-header"><h2>Results</h2><p>Select a domain to browse scan artifacts.</p></div>
        {sessions.length > 0 ? (
          <div className="session-list">
            {sessions.map(s => (
              <div key={s.domain} className="session-item" onClick={() => setActiveDomain(s.domain)}>
                <div><div className="session-domain">{s.domain}</div><div className="session-meta">{s.timestamp || 'No timestamp'}</div></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state"><FolderOpen /><h3>No scan data found</h3><p>Run a scan first to see results here.</p></div>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h2>Results — {activeDomain}</h2>
        <p>Browse all scan artifacts and output files.</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16 }}>
        <div className="card" style={{ maxHeight: 'calc(100vh - 180px)', overflowY: 'auto' }}>
          <div className="card-title" style={{ marginBottom: 12 }}><FolderOpen size={16} /> File Tree</div>
          {loading ? <div className="spinner" /> : artifacts.length > 0 ? (
            <FileTree items={artifacts} onSelect={handleSelect} selectedPath={selected?.path} />
          ) : (
            <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>{error || 'No files found.'}</div>
          )}
        </div>
        <div className="card" style={{ maxHeight: 'calc(100vh - 180px)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {content ? (
            <>
              <div className="card-header">
                <div className="card-title"><FileText size={16} /> {content.name}</div>
                <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{(content.size || 0).toLocaleString()} chars</span>
              </div>
              <div className="file-viewer" style={{ flex: 1 }}>{content.content}</div>
            </>
          ) : (
            <div className="empty-state"><File /><h3>Select a file</h3><p>Click a file in the tree to preview its contents.</p></div>
          )}
        </div>
      </div>
    </div>
  );
}
