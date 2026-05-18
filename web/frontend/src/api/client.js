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

/**
 * Creates a managed WebSocket wrapper with automatic reconnection.
 *
 * @param {function} onMessage  - called with parsed JSON messages
 * @param {object}   socketRef  - React ref whose .current will be updated
 *                                whenever the underlying socket reconnects,
 *                                so callers always send on the live socket.
 */
export function createScanSocket(onMessage, socketRef) {
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
        // Reconnect and update the caller's ref so send() stays live
        const newSock = createScanSocket(onMessage, socketRef);
        if (socketRef) socketRef.current = newSock;
      }
    }, 2000);
  };

  const wrapper = {
    close: () => { ws._shouldReconnect = false; ws.close(); },
    send: (data) => { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(data)); },
  };

  return wrapper;
}
