import { useState, useEffect, useRef, useCallback } from 'react';
import { createScanSocket } from '../api/client';

export function useWebSocket() {
  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef(null);

  const connect = useCallback(() => {
    // Guard: if we already have a live socket, don't create another.
    // socketRef.current is the custom wrapper { close, send } returned by
    // createScanSocket. The wrapper's inner WebSocket may have reconnected
    // automatically (handled inside client.js), so we only skip if the
    // wrapper itself already exists.
    if (socketRef.current) return;

    const sock = createScanSocket(
      (msg) => {
        if (msg.type === 'logs' && msg.lines?.length) {
          setLogs(prev => [...prev, ...msg.lines]);
        }
        if (msg.type === 'status') {
          setStatus(msg.data);
        }
      },
      // Pass the ref so the auto-reconnect inside client.js can update it
      socketRef,
    );

    socketRef.current = sock;
    setConnected(true);
  }, []);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
      setConnected(false);
    }
  }, []);

  const sendAbort = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.send({ action: 'abort' });
    }
  }, []);

  const clearLogs = useCallback(() => setLogs([]), []);

  // Cleanup on unmount
  useEffect(() => () => disconnect(), [disconnect]);

  return { logs, status, connected, connect, disconnect, sendAbort, clearLogs };
}
