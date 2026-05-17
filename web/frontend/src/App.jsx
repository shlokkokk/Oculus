import { useState, useEffect, useCallback } from 'react';
import { VIEWS } from './utils/constants';
import { useWebSocket } from './hooks/useWebSocket';
import { useScan } from './hooks/useScan';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import SafetyBanner from './components/SafetyBanner';
import ScanConfigurator from './components/ScanConfigurator';
import ScanProgress from './components/ScanProgress';
import ResultsViewer from './components/ResultsViewer';
import ReportViewer from './components/ReportViewer';
import ToolStatus from './components/ToolStatus';
import SessionHistory from './components/SessionHistory';

export default function App() {
  const [view, setView] = useState(VIEWS.SCAN);
  const ws = useWebSocket();
  const scan = useScan();

  // Sync WS status into scan hook
  useEffect(() => {
    if (ws.status) scan.updateFromStatus(ws.status);
  }, [ws.status]);

  // Auto-connect WS when scan starts, auto-switch to live view
  const handleStartScan = useCallback(async (config) => {
    ws.clearLogs();
    ws.connect();
    const res = await scan.startScan(config);
    setView(VIEWS.LIVE);
    return res;
  }, [ws, scan]);

  const handleStopScan = useCallback(async () => {
    await scan.stopScan();
    ws.sendAbort();
  }, [scan, ws]);

  // Connect WS on mount if scan is already running
  useEffect(() => {
    if (scan.scanState === 'running' && !ws.connected) {
      ws.connect();
    }
  }, [scan.scanState]);

  const renderView = () => {
    switch (view) {
      case VIEWS.SCAN:
        return <ScanConfigurator onStartScan={handleStartScan} scanState={scan.scanState} />;
      case VIEWS.LIVE:
        return (
          <ScanProgress
            scanState={scan.scanState}
            scanMode={scan.scanMode}
            currentPhase={scan.currentPhase}
            currentModule={scan.currentModule}
            elapsed={scan.elapsed}
            modulesCompleted={scan.modulesCompleted}
            modulesFailed={scan.modulesFailed}
            totalModules={scan.totalModules}
            logs={ws.logs}
            onStop={handleStopScan}
            onReconfigure={() => setView(VIEWS.SCAN)}
          />
        );
      case VIEWS.RESULTS:
        return <ResultsViewer domain={scan.scanDomain} />;
      case VIEWS.REPORTS:
        return <ReportViewer domain={scan.scanDomain} />;
      case VIEWS.TOOLS:
        return <ToolStatus />;
      case VIEWS.HISTORY:
        return <SessionHistory onSelectDomain={(d) => { setView(VIEWS.RESULTS); }} />;
      default:
        return <ScanConfigurator onStartScan={handleStartScan} scanState={scan.scanState} />;
    }
  };

  return (
    <div className="app-layout">
      <Sidebar activeView={view} onNavigate={setView} />
      <TopBar scanState={scan.scanState} scanDomain={scan.scanDomain} elapsed={scan.elapsed} />
      <main className="main-content">
        <SafetyBanner />
        {renderView()}
      </main>
    </div>
  );
}
