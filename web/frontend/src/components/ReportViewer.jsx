import { useState, useEffect } from 'react';
import { FileText, Code, FileCode, FileSearch, Image as ImageIcon, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { api } from '../api/client';

const TABS = [
  { id: 'html', label: 'HTML Report', icon: FileCode },
  { id: 'json', label: 'JSON', icon: Code },
  { id: 'md', label: 'Markdown', icon: FileText },
  { id: 'summary', label: 'Summary', icon: FileSearch },
  { id: 'screenshots', label: 'Screenshots', icon: ImageIcon },
];

const IMAGE_EXTENSIONS = new Set(['.png', '.jpg', '.jpeg', '.webp', '.gif']);

function flattenArtifacts(items, bucket = []) {
  for (const item of items || []) {
    if (item.is_dir) {
      flattenArtifacts(item.children || [], bucket);
      continue;
    }
    const dot = item.name.lastIndexOf('.');
    const ext = dot >= 0 ? item.name.slice(dot).toLowerCase() : '';
    if (IMAGE_EXTENSIONS.has(ext)) {
      bucket.push(item);
    }
  }
  return bucket;
}

function inferScreenshotDomain(shot, fallbackDomain) {
  const raw = `${shot.path}/${shot.name}`.toLowerCase();
  let decoded = raw;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    decoded = raw;
  }
  const urlMatch = decoded.match(/https?:[/_:.-]+(?:www\.)?([a-z0-9][a-z0-9.-]+\.[a-z]{2,})(?:[/_:.-]|$)/i);
  if (urlMatch) return urlMatch[1];

  const hostMatch = decoded.match(/([a-z0-9][a-z0-9-]*(?:[._-][a-z0-9-]+)+[._-](?:com|net|org|io|co|dev|app|in|ai|me|edu|gov|info|biz))/i);
  if (hostMatch) return hostMatch[1].replace(/[_-]/g, '.').replace(/^www\./, '');

  return fallbackDomain || 'screenshots';
}

function groupScreenshots(shots, domain) {
  const groups = new Map();
  shots.forEach((shot) => {
    const key = inferScreenshotDomain(shot, domain);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(shot);
  });
  return [...groups.entries()]
    .map(([name, groupShots]) => ({ name, shots: groupShots.sort((a, b) => a.path.localeCompare(b.path)) }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function buildArtifactUrl(domain, filePath) {
  const safePath = filePath.split('/').map(encodeURIComponent).join('/');
  return `/api/results/${encodeURIComponent(domain)}/file/${safePath}`;
}

export default function ReportViewer({ domain }) {
  const [activeTab, setActiveTab] = useState('html');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [artifacts, setArtifacts] = useState([]);
  const [selectedShotIndex, setSelectedShotIndex] = useState(null);
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
    setSelectedShotIndex(null);

    if (activeTab === 'screenshots') {
      api.listResults(activeDomain)
        .then(r => {
          setArtifacts(r.artifacts || []);
          setContent('');
        })
        .catch(e => {
          setArtifacts([]);
          setContent('');
          setError(e.message);
        })
        .finally(() => setLoading(false));
      return;
    }

    api.getReport(activeDomain, activeTab)
      .then(r => { setContent(r.content || ''); setArtifacts([]); })
      .catch(e => { setContent(''); setArtifacts([]); setError(e.message); })
      .finally(() => setLoading(false));
  }, [activeDomain, activeTab]);

  const screenshots = flattenArtifacts(artifacts);
  const screenshotGroups = groupScreenshots(screenshots, activeDomain);
  const selectedShot = selectedShotIndex === null ? null : screenshots[selectedShotIndex];
  const showPrevShot = () => setSelectedShotIndex((selectedShotIndex - 1 + screenshots.length) % screenshots.length);
  const showNextShot = () => setSelectedShotIndex((selectedShotIndex + 1) % screenshots.length);

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
        <p>View generated HTML, JSON, Markdown, summary reports, and captured screenshots.</p>
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
      ) : activeTab === 'screenshots' ? (
        screenshots.length > 0 ? (
          <div className="screenshot-gallery-wrap">
            <div className="screenshot-gallery-meta">
              <span>{screenshots.length} screenshot{screenshots.length === 1 ? '' : 's'}</span>
              <span>Click any screenshot to open the full viewer.</span>
            </div>
            {screenshotGroups.map(group => (
              <section key={group.name} className="screenshot-domain-section">
                <div className="screenshot-domain-head">
                  <span>{group.name}</span>
                  <strong>{group.shots.length}</strong>
                </div>
                <div className="screenshot-grid screenshot-grid-large">
                  {group.shots.map((shot) => {
                    const index = screenshots.findIndex(s => s.path === shot.path);
                    return (
                      <button
                        key={shot.path}
                        type="button"
                        className="screenshot-card"
                        onClick={() => setSelectedShotIndex(index)}
                      >
                        <div className="screenshot-card-head">
                          <span>{shot.name}</span>
                          <span>{((shot.size || 0) / 1024).toFixed(1)}K</span>
                        </div>
                        <div className="screenshot-card-body">
                          <img
                            src={buildArtifactUrl(activeDomain, shot.path)}
                            alt={shot.name}
                            loading="lazy"
                          />
                        </div>
                      </button>
                    );
                  })}
                </div>
              </section>
            ))}
            {selectedShot && (
              <div className="screenshot-lightbox" onClick={() => setSelectedShotIndex(null)}>
                <div className="screenshot-lightbox-shell" onClick={(e) => e.stopPropagation()}>
                  <div className="screenshot-lightbox-head">
                    <div>
                      <div className="screenshot-lightbox-title">{inferScreenshotDomain(selectedShot, activeDomain)}</div>
                      <div className="screenshot-lightbox-path">{selectedShot.name}</div>
                    </div>
                    <button type="button" className="screenshot-lightbox-close" onClick={() => setSelectedShotIndex(null)} aria-label="Close screenshot viewer">
                      <X size={18} />
                    </button>
                  </div>
                  <div className="screenshot-lightbox-body">
                    {screenshots.length > 1 && (
                      <button type="button" className="screenshot-lightbox-nav prev" onClick={showPrevShot} aria-label="Previous screenshot">
                        <ChevronLeft size={24} />
                      </button>
                    )}
                    <img src={buildArtifactUrl(activeDomain, selectedShot.path)} alt={selectedShot.name} />
                    {screenshots.length > 1 && (
                      <button type="button" className="screenshot-lightbox-nav next" onClick={showNextShot} aria-label="Next screenshot">
                        <ChevronRight size={24} />
                      </button>
                    )}
                  </div>
                  <div className="screenshot-lightbox-foot">
                    <span>{selectedShotIndex + 1} / {screenshots.length}</span>
                    <span>{(selectedShot.size || 0).toLocaleString()} bytes</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="card" style={{ textAlign: 'center', color: 'var(--text-dim)', padding: 40 }}>
            <p>No screenshots found for this domain.</p>
            <p style={{ fontSize: 12, marginTop: 8 }}>Run the screenshot module and refresh the report.</p>
          </div>
        )
      ) : (
        <div className="file-viewer" style={{ maxHeight: 600 }}>{content}</div>
      )}
    </div>
  );
}
