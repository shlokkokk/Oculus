import { useState, useEffect } from 'react';
import { FileText, Code, FileCode, FileSearch } from 'lucide-react';
import { api } from '../api/client';

const TABS = [
  { id: 'html', label: 'HTML Report', icon: FileCode },
  { id: 'json', label: 'JSON', icon: Code },
  { id: 'md', label: 'Markdown', icon: FileText },
  { id: 'summary', label: 'Summary', icon: FileSearch },
];

export default function ReportViewer({ domain }) {
  const [activeTab, setActiveTab] = useState('html');
  const [content, setContent] = useState('');
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
    setError('');
    api.getReport(activeDomain, activeTab)
      .then(r => setContent(r.content || ''))
      .catch(e => { setContent(''); setError(e.message); })
      .finally(() => setLoading(false));
  }, [activeDomain, activeTab]);

  if (!activeDomain) {
    return (
      <div>
        <div className="page-header"><h2>Reports</h2><p>Select a domain to view generated reports.</p></div>
        {sessions.length > 0 ? (
          <div className="session-list">
            {sessions.map(s => (
              <div key={s.domain} className="session-item" onClick={() => setActiveDomain(s.domain)}>
                <div><div className="session-domain">{s.domain}</div><div className="session-meta">{s.timestamp || 'No data'}</div></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state"><FileText /><h3>No reports yet</h3><p>Run a scan and generate reports to view them here.</p></div>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h2>Reports — {activeDomain}</h2>
        <p>View generated HTML, JSON, Markdown, and summary reports.</p>
      </div>

      <div className="tabs">
        {TABS.map(tab => {
          const Icon = tab.icon;
          return (
            <div key={tab.id} className={`tab ${activeTab === tab.id ? 'active' : ''}`} onClick={() => setActiveTab(tab.id)}>
              <Icon size={13} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
              {tab.label}
            </div>
          );
        })}
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><div className="spinner" /></div>
      ) : error ? (
        <div className="card" style={{ textAlign: 'center', color: 'var(--text-dim)', padding: 40 }}>
          <p>Report not available: {error}</p>
          <p style={{ fontSize: 12, marginTop: 8 }}>Run the scan and generate reports first.</p>
        </div>
      ) : activeTab === 'html' ? (
        <iframe
          className="report-frame"
          srcDoc={content}
          title="HTML Report"
          sandbox="allow-scripts"
        />
      ) : (
        <div className="file-viewer" style={{ maxHeight: 600 }}>{content}</div>
      )}
    </div>
  );
}
