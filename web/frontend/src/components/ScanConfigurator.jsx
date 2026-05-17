import { useState, useEffect } from 'react';
import { Play, Zap, Layers, Globe, Settings, ShieldAlert, Flame, EyeOff, RotateCcw } from 'lucide-react';
import { SCAN_MODES, MODULES } from '../utils/constants';
import { api } from '../api/client';
import ModuleSelector from './ModuleSelector';

const ICONS = { Zap, Layers, Globe, Settings };

export default function ScanConfigurator({ onStartScan, scanState }) {
  const [domain, setDomain] = useState('');
  const [mode, setMode] = useState('quick');
  const [modules, setModules] = useState([]);
  const [threads, setThreads] = useState(50);
  const [rateLimit, setRateLimit] = useState(150);
  const [timeout, setTimeout_] = useState(300);
  const [jitter, setJitter] = useState(false);
  const [severity, setSeverity] = useState('low,medium,high,critical');
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');
  const [configLoaded, setConfigLoaded] = useState(false);

  useEffect(() => {
    api.getConfig().then(cfg => {
      setThreads(cfg.threads);
      setRateLimit(cfg.rate_limit);
      setTimeout_(cfg.timeout);
      setJitter(cfg.jitter);
      setSeverity(cfg.nuclei_severity);
      setConfigLoaded(true);
    }).catch(() => setConfigLoaded(true));
  }, []);

  const domainValid = /^[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/.test(domain);
  const canStart = domainValid && scanState !== 'running' && (mode !== 'custom' || modules.length > 0);

  const handleStart = () => {
    setError('');
    setShowConfirm(false);
    onStartScan({
      domain,
      mode,
      modules: mode === 'custom' ? modules : [],
      threads,
      rate_limit: rateLimit,
      timeout: timeout,
      jitter,
      severity,
    }).catch(err => setError(err.message));
  };

  return (
    <div>
      <div className="page-header">
        <h2>Configure Scan</h2>
        <p>Set your target, choose a scan mode, and adjust parameters.</p>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="input-group">
          <label>Target Domain</label>
          <input
            className="input"
            type="text"
            placeholder="example.com"
            value={domain}
            onChange={e => setDomain(e.target.value.trim().toLowerCase())}
            disabled={scanState === 'running'}
          />
          {domain && !domainValid && (
            <span style={{ fontSize: 11, color: 'var(--accent-red)', marginTop: 4, display: 'block' }}>
              Enter a valid domain (e.g. example.com)
            </span>
          )}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title" style={{ marginBottom: 12 }}>Scan Mode</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8 }}>
          {SCAN_MODES.map(m => {
            const Icon = ICONS[m.icon];
            return (
              <div
                key={m.id}
                className={`module-card ${mode === m.id ? 'selected' : ''}`}
                onClick={() => { if (scanState !== 'running') setMode(m.id); }}
                style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 6, padding: 14 }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Icon size={16} />
                  <span className="module-name" style={{ fontSize: 13 }}>{m.name}</span>
                </div>
                <span className="module-tool">{m.desc}</span>
              </div>
            );
          })}
        </div>
      </div>

      {mode === 'custom' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-title" style={{ marginBottom: 12 }}>Select Modules ({modules.length} selected)</div>
          <ModuleSelector selected={modules} onChange={setModules} disabled={scanState === 'running'} />
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title" style={{ marginBottom: 12 }}>Configuration</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
          <div className="input-group" style={{ marginBottom: 0 }}>
            <label>Threads</label>
            <input className="input" type="number" min="1" max="500" value={threads}
              onChange={e => setThreads(Number(e.target.value))} disabled={scanState === 'running'} />
          </div>
          <div className="input-group" style={{ marginBottom: 0 }}>
            <label>Rate Limit</label>
            <input className="input" type="number" min="1" max="10000" value={rateLimit}
              onChange={e => setRateLimit(Number(e.target.value))} disabled={scanState === 'running'} />
          </div>
          <div className="input-group" style={{ marginBottom: 0 }}>
            <label>Timeout (s)</label>
            <input className="input" type="number" min="10" max="7200" value={timeout}
              onChange={e => setTimeout_(Number(e.target.value))} disabled={scanState === 'running'} />
          </div>

          <div className="input-group" style={{ gridColumn: 'span 2', marginBottom: 0 }}>
            <label>Nuclei Severity</label>
            <select className="input" value={severity} onChange={e => setSeverity(e.target.value)} disabled={scanState === 'running'}>
              <option value="low,medium,high,critical">All</option>
              <option value="medium,high,critical">Medium+</option>
              <option value="high,critical">High + Critical</option>
              <option value="critical">Critical only</option>
            </select>
          </div>
          <div className="input-group" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', marginBottom: 0 }}>
            <div className="toggle-row" style={{ height: '42px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'rgba(255,255,255,0.01)', boxSizing: 'border-box' }}>
              <span className="toggle-label" style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-dim)' }}>Jitter (stealth)</span>
              <div className={`toggle ${jitter ? 'on' : ''}`} onClick={() => { if (scanState !== 'running') setJitter(!jitter); }} style={{ margin: 0 }}>
                <div className="toggle-knob" />
              </div>
            </div>
          </div>
        </div>

        <div style={{ marginTop: '16px', borderTop: '1px dashed var(--border)', paddingTop: '16px' }}>
          <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: '10px' }}>Optimization Presets</div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={scanState === 'running'}
              onClick={() => {
                setThreads(100);
                setRateLimit(300);
                setTimeout_(240);
                setJitter(false);
                setSeverity('low,medium,high,critical');
              }}
              style={{
                fontSize: '11px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                borderRadius: '6px',
                background: 'rgba(168,85,247,0.04)',
                border: '1px solid rgba(168,85,247,0.12)',
                color: '#B975FF',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(168,85,247,0.12)';
                e.currentTarget.style.borderColor = 'rgba(168,85,247,0.3)';
                e.currentTarget.style.boxShadow = '0 0 10px rgba(168,85,247,0.15)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(168,85,247,0.04)';
                e.currentTarget.style.borderColor = 'rgba(168,85,247,0.12)';
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              <ShieldAlert size={13} />
              Kali Linux Native
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={scanState === 'running'}
              onClick={() => {
                setThreads(200);
                setRateLimit(800);
                setTimeout_(300);
                setJitter(false);
                setSeverity('low,medium,high,critical');
              }}
              style={{
                fontSize: '11px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                borderRadius: '6px',
                background: 'rgba(16,185,129,0.04)',
                border: '1px solid rgba(16,185,129,0.12)',
                color: 'var(--accent-green)',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(16,185,129,0.12)';
                e.currentTarget.style.borderColor = 'rgba(16,185,129,0.3)';
                e.currentTarget.style.boxShadow = '0 0 10px rgba(16,185,129,0.15)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(16,185,129,0.04)';
                e.currentTarget.style.borderColor = 'rgba(16,185,129,0.12)';
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              <Flame size={13} />
              High Performance
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={scanState === 'running'}
              onClick={() => {
                setThreads(15);
                setRateLimit(50);
                setTimeout_(600);
                setJitter(true);
                setSeverity('high,critical');
              }}
              style={{
                fontSize: '11px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                borderRadius: '6px',
                background: 'rgba(245,158,11,0.04)',
                border: '1px solid rgba(245,158,11,0.12)',
                color: 'var(--accent-amber)',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(245,158,11,0.12)';
                e.currentTarget.style.borderColor = 'rgba(245,158,11,0.3)';
                e.currentTarget.style.boxShadow = '0 0 10px rgba(245,158,11,0.15)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(245,158,11,0.04)';
                e.currentTarget.style.borderColor = 'rgba(245,158,11,0.12)';
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              <EyeOff size={13} />
              Stealth Operations
            </button>

            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={scanState === 'running'}
              onClick={() => {
                api.getConfig().then(cfg => {
                  setThreads(cfg.threads || 50);
                  setRateLimit(cfg.rate_limit || 150);
                  setTimeout_(cfg.timeout || 300);
                  setJitter(cfg.jitter || false);
                  setSeverity(cfg.nuclei_severity || 'low,medium,high,critical');
                });
              }}
              style={{
                marginLeft: 'auto',
                fontSize: '11px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                borderRadius: '6px',
                background: 'rgba(239,68,68,0.04)',
                border: '1px solid rgba(239,68,68,0.12)',
                color: 'var(--accent-red)',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(239,68,68,0.12)';
                e.currentTarget.style.borderColor = 'rgba(239,68,68,0.3)';
                e.currentTarget.style.boxShadow = '0 0 10px rgba(239,68,68,0.15)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(239,68,68,0.04)';
                e.currentTarget.style.borderColor = 'rgba(239,68,68,0.12)';
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              <RotateCcw size={13} />
              Reset to Defaults
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div style={{ color: 'var(--accent-red)', fontSize: 13, marginBottom: 12, padding: '8px 12px', background: 'rgba(239,68,68,0.1)', borderRadius: 6 }}>
          {error}
        </div>
      )}

      <button
        className="btn btn-primary"
        disabled={!canStart}
        onClick={() => setShowConfirm(true)}
        style={{ width: '100%', padding: '14px 20px', fontSize: 14 }}
      >
        <Play size={16} />
        {scanState === 'running' ? 'Scan in Progress...' : 'Start Scan'}
      </button>

      {showConfirm && (
        <div className="overlay" onClick={() => setShowConfirm(false)}>
          <div className="dialog" onClick={e => e.stopPropagation()}>
            <h3>Confirm Scan Launch</h3>
            <p>
              You are about to scan <strong style={{ color: 'var(--accent)' }}>{domain}</strong> using{' '}
              <strong>{SCAN_MODES.find(m => m.id === mode)?.name}</strong> mode.
              {mode === 'custom' && ` (${modules.length} modules selected)`}
              <br /><br />
              Ensure you have authorization to scan this target.
            </p>
            <div className="dialog-actions">
              <button className="btn btn-ghost" onClick={() => setShowConfirm(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleStart}>
                <Play size={14} /> Launch Scan
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
