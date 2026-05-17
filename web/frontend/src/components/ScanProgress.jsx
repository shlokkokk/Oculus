import { useState } from 'react';
import { StopCircle, CheckCircle2, XCircle, Loader, ShieldCheck, ShieldAlert } from 'lucide-react';
import Terminal from './Terminal';

export default function ScanProgress({ scanState, scanMode, currentPhase, currentModule, elapsed, modulesCompleted, modulesFailed, totalModules, logs, onStop, onReconfigure }) {
  const [showConfirmAbort, setShowConfirmAbort] = useState(false);
  const isCompleted = scanState === 'completed';
  const progress = isCompleted ? 100 : (totalModules > 0 ? Math.round((modulesCompleted.length / totalModules) * 100) : 0);
  const isRunning = scanState === 'running';

  const fmtTime = (s) => {
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    return h > 0 ? `${h}h ${m}m ${sec}s` : m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)', boxSizing: 'border-box' }}>
      <div className="page-header" style={{ marginBottom: 12, flexShrink: 0 }}>
        <h2>Live Output</h2>
        <p>{isRunning ? `Scanning — ${currentModule || 'initializing'}` : scanState === 'idle' ? 'No active scan' : `Scan ${scanState}`}</p>
      </div>

      {scanState !== 'idle' && (
        <div className="card" style={{ marginBottom: 16, flexShrink: 0 }}>
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
                <button className="btn btn-danger btn-sm" onClick={() => setShowConfirmAbort(true)}>
                  <StopCircle size={14} /> Abort
                </button>
              )}
              {!isRunning && onReconfigure && (
                <button className="btn btn-ghost btn-sm" onClick={onReconfigure} style={{ color: scanState === 'aborted' ? 'var(--accent)' : 'var(--text)' }}>
                   {scanState === 'aborted' ? 'Resume / New Scan' : 'New Scan'}
                </button>
              )}
            </div>
          </div>
          <div className="progress-bar-track">
            <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
          </div>
          <div className="progress-info">
            <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span>{isCompleted ? totalModules : modulesCompleted.length} / {totalModules} {scanMode === 'full_spectrum' ? 'steps' : 'modules'}</span>
              {currentPhase && <span style={{ color: 'var(--accent-blue)', fontWeight: 500, fontSize: 12 }}>— {currentPhase}</span>}
            </span>
            {modulesFailed.length > 0 && <span style={{ color: 'var(--accent-red)' }}>{modulesFailed.length} failed</span>}
            <span>{progress}%</span>
          </div>
          {modulesCompleted.length > 0 && (
            <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 6, maxLines: 2, overflowY: 'auto' }}>
              {modulesCompleted.map(m => (
                <span key={m} style={{ fontSize: 11, padding: '3px 8px', background: 'rgba(16,185,129,0.08)', color: 'var(--accent-green)', borderRadius: 4, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  <ShieldCheck size={10} />{m}
                </span>
              ))}
              {modulesFailed.map(m => (
                <span key={m} style={{ fontSize: 11, padding: '3px 8px', background: 'rgba(239,68,68,0.08)', color: 'var(--accent-red)', borderRadius: 4, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  <ShieldAlert size={10} />{m}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      <Terminal lines={logs} title="oculus" />

      {showConfirmAbort && (
        <div className="overlay" onClick={() => setShowConfirmAbort(false)} style={{ zIndex: 100 }}>
          <div className="dialog" onClick={e => e.stopPropagation()}>
            <h3 style={{ color: 'var(--accent-red)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <ShieldAlert size={20} /> Abort Active Scan?
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: '1.5', marginBottom: '20px' }}>
              You are about to abort the current offensive operation. All active background sub-processes and thread pools will be immediately terminated. This action cannot be undone.
            </p>
            <div className="dialog-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button className="btn btn-ghost" onClick={() => setShowConfirmAbort(false)}>
                Cancel
              </button>
              <button className="btn btn-danger" onClick={() => { setShowConfirmAbort(false); onStop(); }}>
                <StopCircle size={14} /> Yes, Abort Scan
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
