import { useState, useCallback, useEffect, useRef } from 'react';
import { api } from '../api/client';

export function useScan() {
  const [scanState, setScanState] = useState('idle');
  const [scanDomain, setScanDomain] = useState(null);
  const [scanMode, setScanMode] = useState(null);
  const [currentModule, setCurrentModule] = useState(null);
  const [currentPhase, setCurrentPhase] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [modulesCompleted, setModulesCompleted] = useState([]);
  const [modulesFailed, setModulesFailed] = useState([]);
  const [totalModules, setTotalModules] = useState(0);
  const pollRef = useRef(null);

  const updateFromStatus = useCallback((data) => {
    if (!data) return;
    setScanState(data.state || 'idle');
    setScanDomain(data.domain || null);
    setScanMode(data.mode || null);
    setCurrentModule(data.current_module || null);
    setCurrentPhase(data.current_phase || null);
    setElapsed(data.elapsed_seconds || 0);
    setModulesCompleted(data.modules_completed || []);
    setModulesFailed(data.modules_failed || []);
    setTotalModules(data.total_modules || 0);
  }, []);

  const pollStatus = useCallback(async () => {
    try {
      const data = await api.scanStatus();
      updateFromStatus(data);
    } catch {}
  }, [updateFromStatus]);

  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    pollRef.current = setInterval(pollStatus, 1500);
  }, [pollStatus]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startScan = useCallback(async (config) => {
    const res = await api.startScan(config);
    setScanState('running');
    setScanDomain(config.domain);
    setScanMode(config.mode);
    startPolling();
    return res;
  }, [startPolling]);

  const stopScan = useCallback(async () => {
    await api.stopScan();
    setScanState('aborted');
    stopPolling();
  }, [stopPolling]);

  useEffect(() => {
    pollStatus();
    return stopPolling;
  }, [pollStatus, stopPolling]);

  useEffect(() => {
    if (scanState === 'running') startPolling();
    else stopPolling();
  }, [scanState, startPolling, stopPolling]);

  return {
    scanState, scanDomain, scanMode, currentModule, currentPhase,
    elapsed, modulesCompleted, modulesFailed, totalModules,
    startScan, stopScan, pollStatus, updateFromStatus,
  };
}
