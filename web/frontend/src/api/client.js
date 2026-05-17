const BASE = '';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  health: () => request('/api/health'),
  getTools: (force = false) => request(force ? '/api/tools?force=true' : '/api/tools'),
  getConfig: () => request('/api/config'),

  startScan: (data) => request('/api/scan/start', { method: 'POST', body: JSON.stringify(data) }),
  stopScan: () => request('/api/scan/stop', { method: 'POST' }),
  scanStatus: () => request('/api/scan/status'),
  scanLogs: (since = 0) => request(`/api/scan/logs?since=${since}`),

  listSessions: () => request('/api/sessions'),
  getSession: (domain) => request(`/api/sessions/${encodeURIComponent(domain)}`),

  listResults: (domain) => request(`/api/results/${encodeURIComponent(domain)}`),
  searchFiles: (domain, query) => request(`/api/results/${encodeURIComponent(domain)}/search?q=${encodeURIComponent(query)}`),
  getFile: (domain, path) => request(`/api/results/${encodeURIComponent(domain)}/file/${path}`),

  getReport: (domain, fmt) => request(`/api/reports/${encodeURIComponent(domain)}/${fmt}`),
};

export function createScanSocket(onMessage) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const ws = new WebSocket(`${protocol}//${host}/ws/scan`);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch {}
  };

  ws.onerror = () => {};
  ws.onclose = () => {
    setTimeout(() => {
      if (ws._shouldReconnect !== false) {
        createScanSocket(onMessage);
      }
    }, 2000);
  };

  return {
    close: () => { ws._shouldReconnect = false; ws.close(); },
    send: (data) => { if (ws.readyState === 1) ws.send(JSON.stringify(data)); },
  };
}
