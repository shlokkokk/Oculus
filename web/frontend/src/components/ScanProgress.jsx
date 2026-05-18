import { useState, useEffect } from 'react';
import { StopCircle, CheckCircle2, XCircle, Loader, ShieldCheck, ShieldAlert, RotateCcw, Play, X } from 'lucide-react';
import Terminal from './Terminal';
import { api } from '../api/client';

function ResumeModal({ domain, mode, onClose, onLaunch }) {
  const [threads, setThreads] = useState(50);
  const [rateLimit, setRateLimit] = useState(150);
  const [timeout, setTimeout_] = useState(300);
  const [jitter, setJitter] = useState(false);
  const [severity, setSeverity] = useState('low,medium,high,critical');
  const [sqlmapLevel, setSqlmapLevel] = useState(5);
  const [sqlmapRisk, setSqlmapRisk] = useState(3);
  const [sqlmapThreads, setSqlmapThreads] = useState(10);
  const [sessionData, setSessionData] = useState(null);

  useEffect(() => {
    // Fetch both config and session state in parallel
    Promise.all([
      api.getConfig(),
      api.getSession(domain).catch(() => null)
    ]).then(([cfg, sess]) => {
      setThreads(cfg.threads || 50);
      setRateLimit(cfg.rate_limit || 150);
      setTimeout_(cfg.timeout || 300);
      setJitter(cfg.jitter || false);
      setSeverity(cfg.nuclei_severity || 'low,medium,high,critical');
      setSqlmapLevel(cfg.sqlmap_level ?? 5);
      setSqlmapRisk(cfg.sqlmap_risk ?? 3);
      setSqlmapThreads(Math.min(cfg.sqlmap_threads ?? cfg.threads ?? 10, 10));
      setSessionData(sess);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [domain]);

  const handleLaunch = () => {
    onLaunch({
      domain,
      mode,
      threads: threads === '' ? null : Number(threads),
      rate_limit: rateLimit === '' ? null : Number(rateLimit),
      timeout: timeout === '' ? null : Number(timeout),
      sqlmap_level: sqlmapLevel === '' ? null : Number(sqlmapLevel),
      sqlmap_risk: sqlmapRisk === '' ? null : Number(sqlmapRisk),
      sqlmap_threads: sqlmapThreads === '' ? null : Number(sqlmapThreads),
      jitter,
      severity,
      resume: true,
    });
  };

  return (
    <div className="overlay" style={{ zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(5, 10, 20, 0.8)', backdropFilter: 'blur(10px)' }} onClick={onClose}>
      <div className="dialog" style={{ width: '660px', maxWidth: '95%', background: 'var(--bg-secondary)', border: '1px solid var(--accent)', padding: '32px', borderRadius: 'var(--radius-md)', boxShadow: '0 12px 40px rgba(0,0,0,0.6)', display: 'flex', flexDirection: 'column', gap: '22px' }} onClick={e => e.stopPropagation()}>
        
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: '16px' }}>
          <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--accent)' }}>
            <RotateCcw size={20} />
            Configure & Resume Session
          </h3>
          <X size={20} onClick={onClose} style={{ cursor: 'pointer', opacity: 0.6, transition: 'opacity 0.2s' }} className="hover-opacity-100" />
        </div>

        {/* Description */}
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.6', margin: 0 }}>
          <span>You are resuming the active recon pipeline for <strong style={{ color: 'var(--accent)' }}>{domain}</strong> in <strong style={{ color: 'var(--accent)' }}>{mode}</strong> mode. It will continue precisely from where it was aborted/failed, skipping completed modules to save time.</span>
        </p>

        {/* Operational Banner */}
        <div style={{ 
          padding: '14px 18px', 
          background: 'rgba(245, 158, 11, 0.04)', 
          border: '1px solid rgba(245, 158, 11, 0.15)',
          borderLeft: '4px solid var(--accent-amber)',
          borderRadius: 'var(--radius-sm)',
          fontSize: '12px',
          color: 'var(--accent-amber)',
          lineHeight: '1.55',
          marginTop: '2px',
          marginBottom: '4px'
        }}>
          ⚠️ <strong>Operational Notice:</strong> Completed modules are locked and will be skipped. Changing parameters (like Nuclei severity or SQLMap risk) for already completed modules will not re-run them. To apply new parameters to completed phases, cancel this and select <strong>Start Fresh</strong> instead.
        </div>

        {/* Completed Modules List */}
        {!loading && sessionData?.completed_modules && sessionData.completed_modules.length > 0 && (
          <div style={{
            background: 'var(--bg-primary)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            padding: '12px 16px',
            maxHeight: '120px',
            overflowY: 'auto'
          }}>
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.05em' }}>
              Already Completed ({sessionData.completed_modules.length})
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {sessionData.completed_modules.map(mod => (
                <span key={mod} style={{
                  fontSize: '11px',
                  background: 'rgba(16, 185, 129, 0.08)',
                  color: 'var(--accent-green)',
                  border: '1px solid rgba(16, 185, 129, 0.2)',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}>
                  <CheckCircle2 size={10} /> {mod}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Form Inputs Grid */}
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
            <Loader size={24} className="spinner" />
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            
            {/* Row 1: General Parameters */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px' }}>
              <div className="input-group" style={{ marginBottom: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-dim)', fontWeight: 600 }}>Threads</label>
                <input className="input" type="number" value={threads} onChange={e => setThreads(e.target.value)} style={{ padding: '10px 14px', fontSize: '13px', height: '38px' }} />
              </div>
              <div className="input-group" style={{ marginBottom: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-dim)', fontWeight: 600 }}>Rate Limit (req/s)</label>
                <input className="input" type="number" value={rateLimit} onChange={e => setRateLimit(e.target.value)} style={{ padding: '10px 14px', fontSize: '13px', height: '38px' }} />
              </div>
              <div className="input-group" style={{ marginBottom: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-dim)', fontWeight: 600 }}>Timeout (Seconds)</label>
                <input className="input" type="number" value={timeout} onChange={e => setTimeout_(e.target.value)} style={{ padding: '10px 14px', fontSize: '13px', height: '38px' }} />
              </div>
            </div>

            {/* Row 2: Advanced Cyberpunk Controls */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px' }}>
              <div className="input-group" style={{ gridColumn: 'span 2', marginBottom: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-dim)', fontWeight: 600 }}>Nuclei Severity</label>
                <select className="input" value={severity} onChange={e => setSeverity(e.target.value)} style={{ padding: '0 14px', fontSize: '13px', height: '38px', cursor: 'pointer' }}>
                  <option value="low,medium,high,critical">All</option>
                  <option value="medium,high,critical">Medium+</option>
                  <option value="high,critical">High + Critical</option>
                  <option value="critical">Critical only</option>
                </select>
              </div>
              <div className="input-group" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', marginBottom: 0, gap: '6px' }}>
                <label style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-dim)', fontWeight: 600 }}>Stealth Mode</label>
                <div className="toggle-row" style={{
                  height: '38px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0 12px',
                  border: jitter ? '1px solid rgba(0, 212, 170, 0.35)' : '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  background: jitter ? 'rgba(0, 212, 170, 0.03)' : 'rgba(255,255,255,0.01)',
                  boxShadow: jitter ? '0 0 12px rgba(0, 212, 170, 0.08)' : 'none',
                  boxSizing: 'border-box',
                  transition: 'all 0.3s ease',
                  cursor: 'pointer'
                }} onClick={() => setJitter(!jitter)}>
                  <span className="toggle-label" style={{
                    fontSize: '12px',
                    fontWeight: 600,
                    color: jitter ? 'var(--accent)' : 'var(--text-dim)',
                    textShadow: jitter ? '0 0 6px rgba(0, 212, 170, 0.25)' : 'none',
                    transition: 'all 0.3s ease'
                  }}>
                    Jitter (stealth)
                  </span>
                  <div className={`toggle ${jitter ? 'on' : ''}`} style={{ margin: 0, transition: 'all 0.3s ease' }}>
                    <div className="toggle-knob" style={{ transition: 'all 0.3s ease' }} />
                  </div>
                </div>
              </div>
            </div>

            {/* Sub-Header Divider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '6px', marginBottom: '2px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.08em', color: 'var(--text-dim)', textTransform: 'uppercase' }}>SQLMap Advanced Injection Parameters</span>
              <div style={{ flex: 1, height: '1px', background: 'var(--border)' }}></div>
            </div>

            {/* Row 3: SQLMap Parameters */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
              <div className="input-group" style={{ marginBottom: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-dim)', fontWeight: 600 }}>SQLMap Level</label>
                <input className="input" type="number" min="1" max="5" value={sqlmapLevel} onChange={e => setSqlmapLevel(e.target.value)} style={{ padding: '10px 14px', fontSize: '13px', height: '38px' }} />
              </div>
              <div className="input-group" style={{ marginBottom: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-dim)', fontWeight: 600 }}>SQLMap Risk</label>
                <input className="input" type="number" min="1" max="3" value={sqlmapRisk} onChange={e => setSqlmapRisk(e.target.value)} style={{ padding: '10px 14px', fontSize: '13px', height: '38px' }} />
              </div>
              <div className="input-group" style={{ marginBottom: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-dim)', fontWeight: 600 }}>SQLMap Threads</label>
                <input className="input" type="number" min="1" max="10" value={sqlmapThreads} onChange={e => { const val = e.target.value; setSqlmapThreads(val === '' ? '' : Math.min(Number(val), 10)); }} style={{ padding: '10px 14px', fontSize: '13px', height: '38px' }} />
              </div>
            </div>
          </div>
        )}

        {/* Footer Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', borderTop: '1px solid var(--border)', paddingTop: '20px', marginTop: '10px' }}>
          <button className="btn btn-ghost" onClick={onClose} style={{ padding: '10px 20px', fontSize: '13px', fontWeight: 500, height: '38px' }}>Cancel</button>
          <button 
            className="btn btn-primary" 
            onClick={handleLaunch} 
            disabled={loading}
            style={{ 
              padding: '10px 22px', 
              fontSize: '13px', 
              background: 'var(--accent)', 
              borderColor: 'var(--accent)',
              color: 'var(--bg-primary)',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              height: '38px',
              cursor: 'pointer'
            }}
          >
            <RotateCcw size={14} /> Launch Resume
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ScanProgress({ 
  scanState, 
  scanMode, 
  scanDomain, 
  currentPhase, 
  currentModule, 
  elapsed, 
  modulesCompleted, 
  modulesFailed, 
  totalModules, 
  logs, 
  onStop, 
  onStartScan, 
  onRelaunchFresh,
  onReconfigure 
}) {
  const [showConfirmAbort, setShowConfirmAbort] = useState(false);
  const [showConfirmFresh, setShowConfirmFresh] = useState(false);
  const [showResumeModal, setShowResumeModal] = useState(false);
  
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
              {!isRunning && scanDomain && (
                <div style={{ display: 'flex', gap: 8 }}>
                  {(scanState === 'aborted' || scanState === 'failed') && (
                    <button 
                      className="btn" 
                      onClick={() => setShowResumeModal(true)} 
                      style={{ 
                        padding: '6px 12px', 
                        fontSize: 12, 
                        border: '1.5px solid var(--accent)', 
                        color: 'var(--accent)', 
                        background: 'rgba(0, 212, 170, 0.04)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        cursor: 'pointer'
                      }}
                    >
                      <RotateCcw size={12} /> Resume Scan
                    </button>
                  )}
                  <button 
                    className={`btn ${scanState === 'completed' ? 'btn-ghost' : 'btn-primary'}`}
                    onClick={() => setShowConfirmFresh(true)} 
                    style={{ 
                      padding: '6px 12px', 
                      fontSize: 12, 
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      cursor: 'pointer',
                      ...(scanState === 'completed' ? {
                        border: '1.5px solid var(--border)',
                        color: 'var(--text-secondary)',
                      } : {}),
                    }}
                  >
                    <Play size={12} /> {scanState === 'completed' ? 'New Scan' : 'Start Fresh'}
                  </button>
                </div>
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

      {showConfirmFresh && (
        <div className="overlay" onClick={() => setShowConfirmFresh(false)} style={{ zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(5, 10, 20, 0.75)', backdropFilter: 'blur(6px)' }}>
          <div className="dialog" style={{ width: '500px', padding: '28px', background: 'var(--bg-secondary)', border: `1px solid ${scanState === 'completed' ? 'var(--border)' : 'var(--accent-amber)'}`, borderRadius: 'var(--radius-md)', boxShadow: '0 8px 32px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column', gap: '16px' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: 0, color: scanState === 'completed' ? 'var(--text-primary)' : 'var(--accent-amber)', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '16px', fontWeight: 700 }}>
              <ShieldAlert size={20} /> {scanState === 'completed' ? 'Start a New Scan?' : 'Start Fresh Scan?'}
            </h3>

            {scanState === 'completed' ? (
              /* ── Completed → light "New Scan" dialog ── */
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: '1.6', margin: 0 }}>
                You will be taken to the <strong>Scan Configurator</strong>, pre-populated with{' '}
                <strong style={{ color: 'var(--accent)' }}>{scanDomain}</strong> in{' '}
                <strong>{scanMode === 'full_spectrum' ? 'Full Spectrum' : (scanMode || 'quick') + ' recon'}</strong> mode.
                <br /><br />
                Your completed results are safely stored in{' '}
                <code style={{ background: 'rgba(255,255,255,0.06)', padding: '1px 5px', borderRadius: 3 }}>output-{scanDomain}/</code>.
              </p>
            ) : (
              /* ── Aborted / Failed → warning "Start Fresh" dialog ── */
              <>
                <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: '1.6', margin: 0 }}>
                  You will be taken to the <strong>Scan Configurator</strong> to launch a fully fresh run
                  for <strong style={{ color: 'var(--accent)' }}>{scanDomain}</strong> from Step 1.
                </p>
                <div style={{
                  padding: '10px 14px', borderRadius: 6,
                  background: 'rgba(245,158,11,0.06)',
                  border: '1px solid rgba(245,158,11,0.2)',
                  fontSize: 12, color: 'var(--accent-amber)', lineHeight: 1.6,
                }}>
                  ⚠️ Your partial output in{' '}
                  <code style={{ background: 'rgba(255,255,255,0.06)', padding: '1px 5px', borderRadius: 3 }}>output-{scanDomain}/</code>{' '}
                  will be <strong>automatically backed up</strong> to{' '}
                  <code style={{ background: 'rgba(255,255,255,0.06)', padding: '1px 5px', borderRadius: 3 }}>backup-{scanDomain}/</code>{' '}
                  before the fresh scan begins — nothing is permanently deleted.
                </div>
              </>
            )}

            <div className="dialog-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', borderTop: '1px solid var(--border)', paddingTop: '16px', marginTop: '4px' }}>
              <button className="btn btn-ghost" onClick={() => setShowConfirmFresh(false)} style={{ fontSize: '12px', padding: '8px 16px', height: '36px' }}>
                Cancel
              </button>
              <button 
                className="btn btn-primary" 
                onClick={() => { 
                  setShowConfirmFresh(false); 
                  onRelaunchFresh(scanDomain, scanMode); 
                }}
                style={{ 
                  fontSize: '12px', 
                  padding: '8px 18px', 
                  background: scanState === 'completed' ? 'var(--accent)' : 'var(--accent-amber)', 
                  borderColor: scanState === 'completed' ? 'var(--accent)' : 'var(--accent-amber)',
                  color: 'var(--bg-primary)',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  height: '36px',
                  cursor: 'pointer'
                }}
              >
                <Play size={12} /> {scanState === 'completed' ? 'Go to Configurator' : 'Proceed to Configurator'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showResumeModal && (
        <ResumeModal
          domain={scanDomain}
          mode={scanMode}
          onClose={() => setShowResumeModal(false)}
          onLaunch={(config) => {
            setShowResumeModal(false);
            onStartScan(config);
          }}
        />
      )}
    </div>
  );
}
