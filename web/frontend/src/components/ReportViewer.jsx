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

function CustomMarkdown({ content, domain }) {
  if (!content) return null;

  // Split into paragraphs / blocks
  const blocks = content.split('\n\n');

  const renderTextWithFormatting = (text) => {
    // Replace **bold** with <strong>
    const boldRegex = /\*\*(.*?)\*\*/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = boldRegex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index));
      }
      parts.push(<strong key={match.index} style={{ color: 'var(--accent)', fontWeight: 600 }}>{match[1]}</strong>);
      lastIndex = boldRegex.lastIndex;
    }

    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return parts.length > 0 ? parts : text;
  };

  return (
    <div style={{ 
      color: 'var(--text-secondary)', 
      fontFamily: 'var(--font-sans)', 
      lineHeight: '1.7', 
      fontSize: '14px', 
      padding: '24px', 
      background: 'var(--bg-primary)', 
      border: '1px solid var(--border)', 
      borderRadius: 'var(--radius-md)',
      overflowY: 'auto',
      flexGrow: 1
    }}>
      {blocks.map((block, blockIdx) => {
        const trimmed = block.trim();
        if (!trimmed) return null;

        // 0. Images
        if (trimmed.startsWith('![')) {
          const match = trimmed.match(/^!\[(.*?)\]\((.*?)\)$/);
          if (match) {
            const alt = match[1];
            const src = match[2];
            const finalSrc = src.startsWith('http') 
              ? src 
              : buildArtifactUrl(domain, src);

            return (
              <div key={blockIdx} style={{ margin: '16px 0', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden', maxWidth: '600px' }}>
                <img 
                  src={finalSrc} 
                  alt={alt} 
                  style={{ width: '100%', height: 'auto', display: 'block', maxHeight: '400px', objectFit: 'contain', background: '#07070a' }} 
                />
                <div style={{ padding: '8px 12px', fontSize: '11px', color: 'var(--text-dim)', borderTop: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
                  {alt}
                </div>
              </div>
            );
          }
        }

        // 1. Horizontal Rule
        if (trimmed === '---' || trimmed === '***') {
          return <hr key={blockIdx} style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '24px 0' }} />;
        }

        // 2. Headings
        if (trimmed.startsWith('# ')) {
          return (
            <h1 key={blockIdx} style={{ 
              color: 'var(--accent)', 
              fontSize: '24px', 
              fontWeight: 800, 
              marginTop: '0', 
              marginBottom: '16px',
              borderBottom: '1px solid rgba(0, 212, 170, 0.15)',
              paddingBottom: '8px'
            }}>
              {renderTextWithFormatting(trimmed.slice(2))}
            </h1>
          );
        }
        if (trimmed.startsWith('## ')) {
          return (
            <h2 key={blockIdx} style={{ 
              color: 'var(--text-primary)', 
              fontSize: '18px', 
              fontWeight: 700, 
              marginTop: '24px', 
              marginBottom: '12px'
            }}>
              {renderTextWithFormatting(trimmed.slice(3))}
            </h2>
          );
        }
        if (trimmed.startsWith('### ')) {
          return (
            <h3 key={blockIdx} style={{ 
              color: 'var(--text-primary)', 
              fontSize: '15px', 
              fontWeight: 600, 
              marginTop: '20px', 
              marginBottom: '10px'
            }}>
              {renderTextWithFormatting(trimmed.slice(4))}
            </h3>
          );
        }

        // 3. Bullet List
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          const items = block.split('\n').map(line => line.trim().replace(/^[-*]\s+/, ''));
          return (
            <ul key={blockIdx} style={{ margin: '0 0 16px 20px', padding: '0', listStyleType: 'square' }}>
              {items.map((item, itemIdx) => (
                <li key={itemIdx} style={{ marginBottom: '6px', color: 'var(--text-secondary)' }}>
                  {renderTextWithFormatting(item)}
                </li>
              ))}
            </ul>
          );
        }

        // 4. Tables
        if (trimmed.startsWith('|')) {
          const lines = block.split('\n').map(line => line.trim()).filter(line => line.startsWith('|'));
          if (lines.length >= 2) {
            // Check if second line is a delimiter |---|
            const isTable = lines[1].replace(/[\s\-|:|]/g, '') === '';
            if (isTable) {
              const headers = lines[0].split('|').map(h => h.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
              const rows = lines.slice(2).map(line => 
                line.split('|').map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1)
              );

              return (
                <div key={blockIdx} style={{ overflowX: 'auto', margin: '16px 0', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                    <thead>
                      <tr style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}>
                        {headers.map((h, idx) => (
                          <th key={idx} style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text-dim)' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, rowIdx) => (
                        <tr key={rowIdx} style={{ borderBottom: rowIdx < rows.length - 1 ? '1px solid var(--border)' : 'none', background: rowIdx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)' }}>
                          {row.map((cell, cellIdx) => (
                            <td key={cellIdx} style={{ padding: '10px 14px', color: cellIdx === 0 ? 'var(--text-primary)' : 'var(--accent-blue)', fontFamily: cellIdx === 0 ? 'var(--font-sans)' : 'var(--font-mono)' }}>
                              {renderTextWithFormatting(cell)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            }
          }
        }

        // 5. Standard Paragraph
        const lines = block.split('\n');
        return (
          <p key={blockIdx} style={{ margin: '0 0 16px 0', color: 'var(--text-secondary)' }}>
            {lines.map((line, idx) => (
              <span key={idx}>
                {renderTextWithFormatting(line)}
                {idx < lines.length - 1 && <br />}
              </span>
            ))}
          </p>
        );
      })}
    </div>
  );
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
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)', boxSizing: 'border-box' }}>
      <div className="page-header" style={{ flexShrink: 0 }}>
        <h2>Reports — {activeDomain}</h2>
        <p>View generated HTML, JSON, Markdown, summary reports, and captured screenshots.</p>
      </div>

      <div className="tabs" style={{ flexShrink: 0, marginBottom: 16 }}>
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

      <div style={{ flexGrow: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flexGrow: 1 }}><div className="spinner" /></div>
        ) : error ? (
          <div className="card" style={{ textAlign: 'center', color: 'var(--text-dim)', padding: 40, flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
            <p>Report not available: {error}</p>
            <p style={{ fontSize: 12, marginTop: 8 }}>Run the scan and generate reports first.</p>
          </div>
        ) : activeTab === 'html' ? (
          <iframe
            className="report-frame"
            srcDoc={content}
            title="HTML Report"
            sandbox="allow-scripts"
            style={{ flexGrow: 1, height: '100%', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}
          />
        ) : activeTab === 'screenshots' ? (
          screenshots.length > 0 ? (
            <div className="screenshot-gallery-wrap" style={{ flexGrow: 1, overflowY: 'auto', minHeight: 0 }}>
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
            <div className="card" style={{ textAlign: 'center', color: 'var(--text-dim)', padding: 40, flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
              <p>No screenshots found for this domain.</p>
              <p style={{ fontSize: 12, marginTop: 8 }}>Run the screenshot module and refresh the report.</p>
            </div>
          )
        ) : activeTab === 'md' ? (
          <CustomMarkdown content={content} domain={activeDomain} />
        ) : (
          <div className="file-viewer" style={{ flexGrow: 1, maxHeight: 'none', height: '100%' }}>{content}</div>
        )}
      </div>
    </div>
  );
}
