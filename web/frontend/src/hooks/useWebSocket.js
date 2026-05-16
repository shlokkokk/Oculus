import { useState, useEffect, useRef, useCallback } from 'react';
import { createScanSocket } from '../api/client';

export function useWebSocket() {
  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef(null);

  const connect = useCallback(() => {
    if (socketRef.current) return;
    const sock = createScanSocket((msg) => {
      if (msg.type === 'logs' && msg.lines?.length) {
        setLogs(prev => [...prev, ...msg.lines]);
      }
      if (msg.type === 'status') {
        setStatus(msg.data);
      }
    });
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

  useEffect(() => () => disconnect(), [disconnect]);

  return { logs, status, connected, connect, disconnect, sendAbort, clearLogs };
}
