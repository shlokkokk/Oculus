import { useState, useEffect } from 'react';
import { History, Target, Clock, BarChart3 } from 'lucide-react';
import { api } from '../api/client';

export default function SessionHistory({ onSelectDomain }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listSessions()
      .then(r => setSessions(r.sessions || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="page-header">
        <h2>Scan History</h2>
        <p>Previous scan sessions and their results.</p>
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><div className="spinner" /></div>
      ) : sessions.length === 0 ? (
        <div className="empty-state">
          <History />
          <h3>No scan history</h3>
          <p>Run your first scan to see history here.</p>
        </div>
      ) : (
        <div className="session-list">
          {sessions.map(session => {
            const r = session.results || {};
            return (
              <div key={session.domain} className="session-item" onClick={() => onSelectDomain?.(session.domain)}>
                <div style={{ flex: 1 }}>
                  <div className="session-domain">
                    <Target size={13} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                    {session.domain}
                  </div>
                  <div className="session-meta">
                    <Clock size={10} style={{ display: 'inline', marginRight: 4 }} />
                    {session.timestamp || 'Unknown date'} · v{session.version || '?'}
                  </div>
                </div>
                <div className="session-metrics">
                  {r.subdomains != null && <span>Subs: {r.subdomains}</span>}
                  {r.alive_hosts != null && <span>Alive: {r.alive_hosts}</span>}
                  {r.urls != null && <span>URLs: {r.urls}</span>}
                  {r.vulnerabilities != null && (
                    <span style={{ color: r.vulnerabilities > 0 ? 'var(--accent-red)' : 'var(--text-dim)' }}>
                      Vulns: {r.vulnerabilities}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
