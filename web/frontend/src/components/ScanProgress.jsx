import { StopCircle, CheckCircle2, XCircle, Loader } from 'lucide-react';
import Terminal from './Terminal';

export default function ScanProgress({ scanState, currentModule, elapsed, modulesCompleted, modulesFailed, totalModules, logs, onStop }) {
  const progress = totalModules > 0 ? Math.round((modulesCompleted.length / totalModules) * 100) : 0;
  const isRunning = scanState === 'running';

  const fmtTime = (s) => {
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    return h > 0 ? `${h}h ${m}m ${sec}s` : m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  return (
    <div>
      <div className="page-header">
        <h2>Live Output</h2>
        <p>{isRunning ? `Scanning — ${currentModule || 'initializing'}` : scanState === 'idle' ? 'No active scan' : `Scan ${scanState}`}</p>
      </div>

      {scanState !== 'idle' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div>
              <span style={{ fontSize: 13, fontWeight: 600 }}>
                {isRunning && <><Loader size={14} style={{ display: 'inline', marginRight: 6, animation: 'spin 1s linear infinite' }} />{currentModule}</>}
                {scanState === 'completed' && <><CheckCircle2 size={14} style={{ display: 'inline', marginRight: 6, color: 'var(--accent-green)' }} />Scan Completed</>}
                {scanState === 'failed' && <><XCircle size={14} style={{ display: 'inline', marginRight: 6, color: 'var(--accent-red)' }} />Scan Failed</>}
                {scanState === 'aborted' && <><StopCircle size={14} style={{ display: 'inline', marginRight: 6, color: 'var(--accent-amber)' }} />Scan Aborted</>}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 12, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>{fmtTime(elapsed)}</span>
              {isRunning && (
                <button className="btn btn-danger btn-sm" onClick={onStop}>
                  <StopCircle size={14} /> Abort
                </button>
              )}
            </div>
          </div>
          <div className="progress-bar-track">
            <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
          </div>
          <div className="progress-info">
            <span>{modulesCompleted.length} / {totalModules} modules</span>
            {modulesFailed.length > 0 && <span style={{ color: 'var(--accent-red)' }}>{modulesFailed.length} failed</span>}
            <span>{progress}%</span>
          </div>
          {modulesCompleted.length > 0 && (
            <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {modulesCompleted.map(m => (
                <span key={m} style={{ fontSize: 11, padding: '3px 8px', background: 'rgba(16,185,129,0.1)', color: 'var(--accent-green)', borderRadius: 4 }}>
                  <CheckCircle2 size={10} style={{ display: 'inline', marginRight: 4 }} />{m}
                </span>
              ))}
              {modulesFailed.map(m => (
                <span key={m} style={{ fontSize: 11, padding: '3px 8px', background: 'rgba(239,68,68,0.1)', color: 'var(--accent-red)', borderRadius: 4 }}>
                  <XCircle size={10} style={{ display: 'inline', marginRight: 4 }} />{m}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      <Terminal lines={logs} title="oculus" />
    </div>
  );
}
