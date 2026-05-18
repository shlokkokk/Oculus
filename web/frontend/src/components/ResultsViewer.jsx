import { useState, useEffect } from 'react';
import { FolderOpen, File, FileText, ChevronRight, ChevronDown, Search, Network, X, Globe, Image as ImageIcon } from 'lucide-react';
import { api } from '../api/client';

// Regex escape helper for in-file highlights
function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Inline component to render text with highlighted keywords
function HighlightedText({ text, highlight }) {
  if (!highlight || !highlight.trim()) {
    return <pre style={{ fontFamily: 'inherit', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{text}</pre>;
  }
  
  try {
    const escaped = escapeRegExp(highlight);
    const regex = new RegExp(`(${escaped})`, 'gi');
    const parts = text.split(regex);
    
    return (
      <pre style={{ fontFamily: 'inherit', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
        {parts.map((part, i) => 
          regex.test(part) ? (
            <mark key={i} className="txt-highlight">{part}</mark>
          ) : (
            part
          )
        )}
      </pre>
    );
  } catch (e) {
    return <pre style={{ fontFamily: 'inherit', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{text}</pre>;
  }
}

// Recursive filtering helper function
function filterTree(items, query, forceExpand = {}) {
  if (!query) return { filteredItems: items, forceExpand };
  
  const lowerQuery = query.toLowerCase();
  const filtered = [];
  
  for (const item of items) {
    if (item.is_dir) {
      const { filteredItems: childFiltered } = filterTree(item.children || [], query, forceExpand);
      if (childFiltered.length > 0) {
        filtered.push({
          ...item,
          children: childFiltered
        });
        forceExpand[item.path] = true;
      } else if (item.name.toLowerCase().includes(lowerQuery)) {
        // Keep the empty folder if it matches the query
        filtered.push({
          ...item,
          children: []
        });
      }
    } else {
      if (item.name.toLowerCase().includes(lowerQuery)) {
        filtered.push(item);
      }
    }
  }
  return { filteredItems: filtered, forceExpand };
}

const IMAGE_EXTENSIONS = new Set(['.png', '.jpg', '.jpeg', '.webp', '.gif']);

function isImageArtifact(item) {
  if (!item || item.is_dir) return false;
  const dot = item.name.lastIndexOf('.');
  const ext = dot >= 0 ? item.name.slice(dot).toLowerCase() : '';
  return IMAGE_EXTENSIONS.has(ext);
}

function buildArtifactUrl(domain, filePath) {
  const safePath = filePath.split('/').map(encodeURIComponent).join('/');
  return `/api/results/${encodeURIComponent(domain)}/file/${safePath}`;
}

function flattenScreenshots(items, bucket = []) {
  for (const item of items || []) {
    if (item.is_dir) {
      flattenScreenshots(item.children || [], bucket);
    } else if (isImageArtifact(item) && item.path.toLowerCase().includes('screenshots/')) {
      bucket.push(item);
    }
  }
  return bucket;
}

function inferScreenshotDomain(shot, fallbackDomain) {
  const raw = `${shot.path}/${shot.name}`.toLowerCase();
  const urlMatch = raw.match(/https?[:_-]+[\\/._-]*([a-z0-9][a-z0-9.-]+\.[a-z]{2,})(?:[\\/._:-]|$)/i);
  if (urlMatch) return urlMatch[1].replace(/^www\./, '');

  const hostMatch = raw.match(/([a-z0-9][a-z0-9-]*(?:[._-][a-z0-9-]+)+[._-](?:com|net|org|io|co|dev|app|in|ai|me|edu|gov|info|biz))/i);
  if (hostMatch) return hostMatch[1].replace(/[_-]/g, '.').replace(/^www\./, '');

  const parts = shot.path.split('/');
  const screenshotIndex = parts.findIndex(p => p.toLowerCase() === 'screenshots');
  if (screenshotIndex >= 0 && parts[screenshotIndex + 2]) {
    return parts[screenshotIndex + 2].replace(/[_-]/g, '.').replace(/^www\./, '');
  }
  return fallbackDomain || 'screenshots';
}

function groupScreenshots(items, domain) {
  const groups = new Map();
  flattenScreenshots(items).forEach((shot) => {
    const key = inferScreenshotDomain(shot, domain);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(shot);
  });
  return [...groups.entries()]
    .map(([name, shots]) => ({ name, shots: shots.sort((a, b) => a.path.localeCompare(b.path)) }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function FileTree({ items, onSelect, selectedPath, depth = 0, forceExpand = {} }) {
  const [expanded, setExpanded] = useState({});
  const toggle = (path) => setExpanded(prev => ({ ...prev, [path]: !prev[path] }));

  // Merge the manual toggle state with the search-forced auto-expand state
  const isExpanded = (path) => expanded[path] || forceExpand[path];

  return (
    <div className="file-tree">
      {items.map(item => (
        <div key={item.path}>
          <div
            className={`file-tree-item ${selectedPath === item.path ? 'active' : ''}`}
            style={{ paddingLeft: 8 + depth * 16 }}
            onClick={() => item.is_dir ? toggle(item.path) : onSelect(item)}
          >
            {item.is_dir ? (isExpanded(item.path) ? <ChevronDown size={14} /> : <ChevronRight size={14} />) : <File size={14} />}
            <span style={{ flex: 1 }}>{item.name}</span>
            {!item.is_dir && <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>{(item.size / 1024).toFixed(1)}K</span>}
          </div>
          {item.is_dir && isExpanded(item.path) && item.children && (
            <FileTree items={item.children} onSelect={onSelect} selectedPath={selectedPath} depth={depth + 1} forceExpand={forceExpand} />
          )}
        </div>
      ))}
    </div>
  );
}

// Highly stylized visual node tree map modal
function TreeMapModal({ items, domain, onSelect, onClose, searchQuery, onSearchChange }) {
  const { filteredItems } = filterTree(items, searchQuery, {});

  // Wrap the entire visual tree map under a single Root Domain Node
  const rootNode = {
    name: domain,
    is_dir: true,
    path: 'root-domain',
    children: filteredItems
  };

  const renderMapNode = (item, depth = 0) => {
    const isFolder = item.is_dir;
    const isRoot = item.path === 'root-domain';
    const isHighlighted = searchQuery && item.name.toLowerCase().includes(searchQuery.toLowerCase());

    return (
      <div key={item.path}>
        <div className="map-tree-item-wrapper">
          <div 
            className={`map-capsule-node ${isRoot ? 'root-node' : isFolder ? 'folder-node' : 'file-node'} ${isHighlighted ? 'highlighted' : ''}`}
            onClick={() => (isRoot || isFolder) ? null : onSelect(item)}
          >
            {isRoot ? <Globe size={13} /> : isFolder ? <FolderOpen size={13} /> : <File size={13} />}
            <span>{item.name}</span>
            {!isFolder && !isRoot && <span style={{ fontSize: 9, opacity: 0.6 }}>({(item.size / 1024).toFixed(1)}K)</span>}
          </div>
        </div>
        {isFolder && item.children && item.children.length > 0 && (
          <div className="map-tree-branch">
            {item.children.map(child => renderMapNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="map-overlay" onClick={onClose}>
      <div className="map-dialog-box" onClick={(e) => e.stopPropagation()}>
        <div className="map-header-bar">
          <div className="map-title-text">
            <Network size={18} />
            <span>[ SYSTEM OUTPUT VISUALIZATION MAP ]</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div className="search-container" style={{ marginBottom: 0 }}>
              <Search size={13} className="search-icon-inside" />
              <input
                type="text"
                placeholder="Search map nodes..."
                className="search-input-field"
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
                style={{ width: 240 }}
              />
            </div>
            <button className="btn btn-ghost btn-sm" onClick={onClose} style={{ padding: '6px 10px' }}>
              <X size={14} />
            </button>
          </div>
        </div>
        <div className="map-view-body">
          {filteredItems.length > 0 ? (
            <div className="map-node-tree">
              {renderMapNode(rootNode)}
            </div>
          ) : (
            <div className="empty-state">
              <Search />
              <h3>No matching nodes</h3>
              <p>Try searching for directories like "nuclei" or files like "alive.txt"</p>
            </div>
          )}
        </div>
      </div>
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
  const [searchQuery, setSearchQuery] = useState('');
  const [fileSearchQuery, setFileSearchQuery] = useState('');
  const [isMapOpen, setIsMapOpen] = useState(false);

  // Global Search states
  const [activeTab, setActiveTab] = useState('explorer');
  const [globalSearchQuery, setGlobalSearchQuery] = useState('');
  const [globalSearchResults, setGlobalSearchResults] = useState([]);
  const [globalSearchLoading, setGlobalSearchLoading] = useState(false);

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

  // Dynamic global search debounce logic (400ms delay to protect backend)
  useEffect(() => {
    if (!globalSearchQuery.trim() || !activeDomain) {
      setGlobalSearchResults([]);
      return;
    }
    const delay = setTimeout(() => {
      setGlobalSearchLoading(true);
      api.searchFiles(activeDomain, globalSearchQuery)
        .then(r => setGlobalSearchResults(r.results || []))
        .catch(() => setGlobalSearchResults([]))
        .finally(() => setGlobalSearchLoading(false));
    }, 400);
    return () => clearTimeout(delay);
  }, [globalSearchQuery, activeDomain]);

  const handleSelect = async (item) => {
    setSelected(item);
    setContent(null);
    setFileSearchQuery(''); // Reset the in-file search box
    setIsMapOpen(false); // Smoothly close the popup on selection
    if (isImageArtifact(item)) {
      setContent({
        type: 'image',
        name: item.name,
        path: item.path,
        size: item.size,
        url: buildArtifactUrl(activeDomain, item.path)
      });
      return;
    }
    try {
      const data = await api.getFile(activeDomain, item.path);
      setContent(data);
    } catch (e) {
      setContent({ content: `Error loading file: ${e.message}`, type: 'text', name: item.name });
    }
  };

  const handleGlobalResultSelect = async (res, forceHighlightText = null) => {
    setSelected({ name: res.name, path: res.path, is_dir: false });
    setContent(null);
    // Set both the local search input AND trigger highlights
    setFileSearchQuery(forceHighlightText || globalSearchQuery);
    try {
      const data = await api.getFile(activeDomain, res.path);
      setContent(data);
    } catch (e) {
      setContent({ content: `Error loading file: ${e.message}`, type: 'text', name: res.name });
    }
  };

  // Perform dynamic filtering based on search input
  const { filteredItems, forceExpand } = filterTree(artifacts, searchQuery, {});
  const screenshotGroups = groupScreenshots(artifacts, activeDomain);
  const screenshotCount = screenshotGroups.reduce((total, group) => total + group.shots.length, 0);

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
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)', boxSizing: 'border-box' }}>
      <div className="page-header" style={{ marginBottom: 12, flexShrink: 0 }}>
        <h2>Results — {activeDomain}</h2>
        <p>Browse all scan artifacts and output files.</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '330px 1fr', gap: 16, flex: 1, minHeight: 0, marginBottom: 16 }}>
        <div className="card" style={{ height: '100%', display: 'flex', flexDirection: 'row', padding: 0, boxSizing: 'border-box', overflow: 'hidden' }}>
          
          {/* Modern Sidebar Navigation Rail */}
          <div className="results-rail">
            <button
              className={`results-rail-btn ${activeTab === 'explorer' ? 'active' : ''}`}
              onClick={() => setActiveTab('explorer')}
              title="File Explorer"
            >
              <FolderOpen size={16} />
              <span style={{ fontSize: 9, fontWeight: 600 }}>Files</span>
            </button>
            <button
              className={`results-rail-btn ${activeTab === 'search' ? 'active' : ''}`}
              onClick={() => setActiveTab('search')}
              title="Search Logs"
            >
              <Search size={16} />
              <span style={{ fontSize: 9, fontWeight: 600 }}>Search</span>
            </button>
            <button
              className={`results-rail-btn ${activeTab === 'screenshots' ? 'active' : ''}`}
              onClick={() => setActiveTab('screenshots')}
              title="Screenshots"
            >
              <ImageIcon size={16} />
              <span style={{ fontSize: 9, fontWeight: 600 }}>Shots</span>
            </button>
          </div>

          {/* Sidebar Inner Content Pane */}
          <div style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
            {activeTab === 'explorer' ? (
            <>
              <div className="card-title" style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 700 }}><FolderOpen size={14} /> File Tree</span>
                <button className="map-btn-trigger" onClick={() => setIsMapOpen(true)}>
                  <Network size={11} />
                  <span>Map View</span>
                </button>
              </div>
              
              <div className="search-container">
                <Search size={13} className="search-icon-inside" />
                <input
                  type="text"
                  placeholder="Filter files..."
                  className="search-input-field"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <div style={{ flex: 1, overflowY: 'auto' }}>
                {loading ? <div className="spinner" /> : filteredItems.length > 0 ? (
                  <FileTree items={filteredItems} onSelect={handleSelect} selectedPath={selected?.path} forceExpand={forceExpand} />
                ) : (
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', textAlign: 'center', marginTop: 20 }}>
                    {error || 'No matching files found.'}
                  </div>
                )}
              </div>
            </>
          ) : activeTab === 'search' ? (
            <>
              <div className="card-title" style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 700 }}>
                <Search size={14} /> Global Search
              </div>
              <div className="search-container" style={{ marginBottom: 12 }}>
                <Search size={13} className="search-icon-inside" />
                <input
                  type="text"
                  placeholder="Search in all files..."
                  className="search-input-field"
                  value={globalSearchQuery}
                  onChange={(e) => setGlobalSearchQuery(e.target.value)}
                />
              </div>

              <div style={{ flex: 1, overflowY: 'auto', paddingRight: 4 }}>
                {globalSearchLoading ? (
                  <div style={{ display: 'flex', justifyContent: 'center', margin: '30px 0' }}><div className="spinner" /></div>
                ) : globalSearchResults.length > 0 ? (
                  <div className="global-search-results">
                    {globalSearchResults.map(res => (
                      <div key={res.path} className="search-result-item" style={{ marginBottom: 14, borderBottom: '1px dashed rgba(0, 212, 170, 0.06)', paddingBottom: 10 }}>
                        <div 
                          className="search-result-title" 
                          onClick={() => handleGlobalResultSelect(res)}
                          style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, fontWeight: 600, color: 'var(--accent-blue)', marginBottom: 4 }}
                        >
                          <span style={{ display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}><File size={11} style={{ flexShrink: 0 }} /> {res.name}</span>
                          <span className="badge" style={{ fontSize: 9, background: 'rgba(0, 212, 170, 0.08)', color: 'var(--accent)', border: '1px solid rgba(0, 212, 170, 0.15)', padding: '1px 5px', borderRadius: 4, flexShrink: 0 }}>
                            {res.matches}
                          </span>
                        </div>
                        <div style={{ fontSize: 9, color: 'var(--text-dim)', marginLeft: 17, marginBottom: 6, wordBreak: 'break-all' }}>{res.path}</div>
                        {res.snippets && res.snippets.length > 0 && (
                          <div className="search-snippets" style={{ marginLeft: 17, display: 'flex', flexDirection: 'column', gap: 4 }}>
                            {res.snippets.map((snip, idx) => (
                              <div 
                                key={idx} 
                                className="search-snippet"
                                onClick={() => handleGlobalResultSelect(res, snip.text)}
                                style={{ 
                                  cursor: 'pointer', 
                                  background: 'rgba(255, 255, 255, 0.02)', 
                                  borderLeft: '2.5px solid var(--accent-amber)', 
                                  padding: '3px 6px', 
                                  fontSize: 9.5, 
                                  color: 'var(--text-primary)', 
                                  fontFamily: 'monospace', 
                                  overflow: 'hidden', 
                                  textOverflow: 'ellipsis', 
                                  whiteSpace: 'nowrap' 
                                }}
                                title={`Line ${snip.line}: ${snip.text}`}
                              >
                                <span style={{ color: 'var(--text-dim)', marginRight: 5 }}>L{snip.line}:</span>
                                {snip.text}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : globalSearchQuery.trim() ? (
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', textAlign: 'center', marginTop: 20 }}>No files found containing "{globalSearchQuery}"</div>
                ) : (
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', textAlign: 'center', marginTop: 20 }}>Type keywords to search across all scan logs.</div>
                )}
              </div>
            </>
          ) : (
            <>
              <div className="card-title" style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                <ImageIcon size={14} />
                Screenshot Groups
              </div>
              <div style={{ flex: 1, overflowY: 'auto' }}>
                {screenshotGroups.length > 0 ? (
                  <div className="screenshot-group-list">
                    {screenshotGroups.map(group => (
                      <button
                        key={group.name}
                        type="button"
                        className="screenshot-group-button"
                        onClick={() => {
                          const first = group.shots[0];
                          setSelected(first);
                          setContent({
                            type: 'image',
                            name: first.name,
                            path: first.path,
                            size: first.size,
                            url: buildArtifactUrl(activeDomain, first.path)
                          });
                        }}
                      >
                        <span>{group.name}</span>
                        <strong>{group.shots.length}</strong>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', textAlign: 'center', marginTop: 20 }}>
                    No screenshots found.
                  </div>
                )}
              </div>
            </>
          )}
          </div>
        </div>
        <div className="card" style={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column', boxSizing: 'border-box' }}>
          {activeTab === 'screenshots' ? (
            <div className="results-screenshot-panel">
              <div className="card-header" style={{ marginBottom: 12 }}>
                <div className="card-title"><ImageIcon size={16} /> Screenshots</div>
                <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{screenshotCount} total</span>
              </div>
              {screenshotGroups.length > 0 ? (
                <div className="results-screenshot-scroll">
                  {screenshotGroups.map(group => (
                    <section key={group.name} className="screenshot-domain-section">
                      <div className="screenshot-domain-head">
                        <span>{group.name}</span>
                        <strong>{group.shots.length}</strong>
                      </div>
                      <div className="screenshot-grid">
                        {group.shots.map((shot) => {
                          const isExpanded = selected?.path === shot.path;
                          return (
                            <button
                              key={shot.path}
                              type="button"
                              className={`screenshot-card ${isExpanded ? 'expanded' : ''}`}
                              onClick={() => {
                                setSelected(isExpanded ? null : shot);
                                setContent(isExpanded ? null : {
                                  type: 'image',
                                  name: shot.name,
                                  path: shot.path,
                                  size: shot.size,
                                  url: buildArtifactUrl(activeDomain, shot.path)
                                });
                              }}
                            >
                              <div className="screenshot-card-head">
                                <span>{shot.name}</span>
                                <span>{((shot.size || 0) / 1024).toFixed(1)}K</span>
                              </div>
                              <div className="screenshot-card-body">
                                <img src={buildArtifactUrl(activeDomain, shot.path)} alt={shot.name} loading="lazy" />
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </section>
                  ))}
                </div>
              ) : (
                <div className="empty-state" style={{ flex: 1 }}>
                  <ImageIcon />
                  <h3>No screenshots found</h3>
                  <p>Run the screenshot module and refresh results.</p>
                </div>
              )}
            </div>
          ) : content ? (
            <>
              <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
                <div className="card-title"><FileText size={16} /> {content.name}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div className="search-container" style={{ marginBottom: 0 }}>
                    <Search size={13} className="search-icon-inside" />
                    <input
                      type="text"
                      placeholder="Search in file..."
                      className="search-input-field"
                      value={fileSearchQuery}
                      onChange={(e) => setFileSearchQuery(e.target.value)}
                      style={{ width: 180 }}
                    />
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{(content.size || 0).toLocaleString()} chars</span>
                </div>
              </div>
              {content.type === 'image' ? (
                <div className="image-file-viewer">
                  <img src={content.url} alt={content.name} />
                </div>
              ) : (
                <div className="file-viewer" style={{ flex: 1 }}>
                  <HighlightedText text={content.content} highlight={fileSearchQuery} />
                </div>
              )}
            </>
          ) : (
            <div className="empty-state" style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100%', padding: '40px 20px' }}>
              <File size={48} style={{ opacity: 0.35, marginBottom: 16, color: 'var(--accent)' }} />
              <h3 style={{ fontSize: '15px', color: 'var(--text-primary)', marginBottom: '8px', fontWeight: 600 }}>Select a file</h3>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '320px', margin: '0 auto', opacity: 0.85 }}>Click a file in the tree to preview its contents.</p>
            </div>
          )}
        </div>
      </div>

      {isMapOpen && (
        <TreeMapModal
          items={artifacts}
          domain={activeDomain}
          onSelect={handleSelect}
          onClose={() => setIsMapOpen(false)}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />
      )}
    </div>
  );
}
