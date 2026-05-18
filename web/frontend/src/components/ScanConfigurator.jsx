import { useState, useEffect } from 'react';
import {
  Play, Zap, Layers, Globe, Settings,
  ShieldAlert, Flame, EyeOff, RotateCcw, ChevronDown, ChevronRight, Cpu, Gauge, Clock,
} from 'lucide-react';
import { SCAN_MODES, MODULES, computeDependencyState } from '../utils/constants';
import { api } from '../api/client';
import ModuleSelector from './ModuleSelector';

const ICONS = { Zap, Layers, Globe, Settings };

export default function ScanConfigurator({ onStartScan, scanState, defaultDomain = '', defaultMode = 'quick' }) {
  /* ── Scan identity ── */
  const [domain, setDomain] = useState(defaultDomain);
  const [mode,   setMode]   = useState(defaultMode);

  /* ── Two-set module state ── */
  const [manualModules, setManualModules] = useState([]);  // what the user explicitly picked
  const [autoModules,   setAutoModules]   = useState([]);  // derived from dependencies
  const resolvedModules = [...manualModules, ...autoModules]; // full list sent to backend

  /* ── Dependency notice banner ── */
  const [dependencyNotice, setDependencyNotice] = useState(null);

  /* ── Scan parameters ── */
  const [threads,        setThreads]        = useState(50);
  const [rateLimit,      setRateLimit]      = useState(150);
  const [timeout,        setTimeout_]       = useState(300);
  const [jitter,         setJitter]         = useState(false);
  const [severity,       setSeverity]       = useState('low,medium,high,critical');

  /* ── SQLMap (collapsible) ── */
  const [sqlOpen,        setSqlOpen]        = useState(false);
  const [sqlmapLevel,    setSqlmapLevel]    = useState(5);
  const [sqlmapRisk,     setSqlmapRisk]     = useState(3);
  const [sqlmapThreads,  setSqlmapThreads]  = useState(10);

  /* ── UI ── */
  const [showConfirm, setShowConfirm] = useState(false);
  const [error,       setError]       = useState('');
  const [configLoaded, setConfigLoaded] = useState(false);

  const moduleNameById = Object.fromEntries(MODULES.map(m => [m.id, m.name]));

  /* Sync prop changes (e.g. relaunch from ScanProgress) */
  useEffect(() => {
    if (defaultDomain) setDomain(defaultDomain);
    if (defaultMode)   setMode(defaultMode);
  }, [defaultDomain, defaultMode]);

  /* Load defaults from backend config */
  useEffect(() => {
    api.getConfig().then(cfg => {
      setThreads(cfg.threads       ?? 50);
      setRateLimit(cfg.rate_limit  ?? 150);
      setTimeout_(cfg.timeout      ?? 300);
      setJitter(cfg.jitter         ?? false);
      setSeverity(cfg.nuclei_severity ?? 'low,medium,high,critical');
      setSqlmapLevel(cfg.sqlmap_level   ?? 5);
      setSqlmapRisk(cfg.sqlmap_risk     ?? 3);
      setSqlmapThreads(Math.min(cfg.sqlmap_threads ?? cfg.threads ?? 10, 10));
      setConfigLoaded(true);
    }).catch(() => setConfigLoaded(true));
  }, []);

  /* ─── Module selection ─── */
  const applyModuleSelection = (nextManualIds, trigger) => {
    const { manualIds, autoIds, resolved } = computeDependencyState(nextManualIds);
    setManualModules(manualIds);
    setAutoModules(autoIds);

    if (autoIds.length > 0) {
      // Only show the notice for modules newly auto-added by the latest trigger
      const prevAuto  = new Set(autoModules);
      const newlyAdded = autoIds.filter(id => !prevAuto.has(id));
      if (newlyAdded.length > 0) {
        const addedNames = newlyAdded.map(id => moduleNameById[id] || id);
        setDependencyNotice({
          trigger: trigger && moduleNameById[trigger] ? moduleNameById[trigger] : null,
          addedNames,
        });
      }
    } else {
      setDependencyNotice(null);
    }
  };

  const dismissAllAuto = () => {
    // Remove all auto modules that no longer have a manual dependant
    // (effectively just clear auto — caller can re-add via future selections)
    setAutoModules([]);
    setDependencyNotice(null);
  };

  /* ─── Validation ─── */
  const domainValid = /^[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/.test(domain);
  const canStart = domainValid && scanState !== 'running' && (mode !== 'custom' || resolvedModules.length > 0);

  /* ─── Start ─── */
  const handleStart = () => {
    setError('');
    setShowConfirm(false);
    onStartScan({
      domain,
      mode,
      modules: mode === 'custom' ? resolvedModules : [],
      threads:       threads       === '' ? null : Number(threads),
      rate_limit:    rateLimit     === '' ? null : Number(rateLimit),
      timeout:       timeout       === '' ? null : Number(timeout),
      sqlmap_level:  sqlmapLevel   === '' ? null : Number(sqlmapLevel),
      sqlmap_risk:   sqlmapRisk    === '' ? null : Number(sqlmapRisk),
      sqlmap_threads: sqlmapThreads === '' ? null : Number(sqlmapThreads),
      jitter,
      severity,
      resume: false,
    }).catch(err => setError(err.message));
  };

  /* ─── Preset appliers ─── */
  const applyPreset = (preset) => {
    if (scanState === 'running') return;
    const presets = {
      kali:   { threads: 100,  rateLimit: 300, timeout_: 240, jitter: false, sqlmapLevel: 5, sqlmapRisk: 3, sqlmapThreads: 10, severity: 'low,medium,high,critical' },
      fast:   { threads: 200,  rateLimit: 800, timeout_: 300, jitter: false, sqlmapLevel: 5, sqlmapRisk: 3, sqlmapThreads: 10, severity: 'low,medium,high,critical' },
      stealth:{ threads: 15,   rateLimit: 50,  timeout_: 600, jitter: true,  sqlmapLevel: 3, sqlmapRisk: 1, sqlmapThreads: 3,  severity: 'high,critical' },
    };
    const p = presets[preset];
    setThreads(p.threads); setRateLimit(p.rateLimit); setTimeout_(p.timeout_);
    setJitter(p.jitter); setSqlmapLevel(p.sqlmapLevel); setSqlmapRisk(p.sqlmapRisk);
    setSqlmapThreads(p.sqlmapThreads); setSeverity(p.severity);
  };

  const resetToDefaults = () => {
    if (scanState === 'running') return;
    api.getConfig().then(cfg => {
      setThreads(cfg.threads || 50); setRateLimit(cfg.rate_limit || 150);
      setTimeout_(cfg.timeout || 300); setJitter(cfg.jitter || false);
      setSeverity(cfg.nuclei_severity || 'low,medium,high,critical');
      setSqlmapLevel(cfg.sqlmap_level || 5); setSqlmapRisk(cfg.sqlmap_risk || 3);
      setSqlmapThreads(cfg.sqlmap_threads || 10);
    });
  };

  const inputNum = (setter, min, max) => (e) => {
    const v = e.target.value;
    setter(v === '' ? '' : Math.min(Math.max(Number(v), min), max));
  };

  /* ───────────────────────────────────────────────────────────────── */
  return (
    <div>
      <div className="page-header">
        <h2>Configure Scan</h2>
        <p>Set your target, choose a scan mode, and tune parameters.</p>
      </div>

      {/* ── Target Domain ── */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="input-group" style={{ marginBottom: 0 }}>
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

      {/* ── Scan Mode ── */}
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

      {/* ── Custom Module Picker ── */}
      {mode === 'custom' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <div className="card-title" style={{ marginBottom: 0 }}>
              Select Modules
              <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--text-dim)', fontWeight: 400 }}>
                {manualModules.length} manual, {autoModules.length} auto-added
              </span>
            </div>
            {resolvedModules.length > 0 && (
              <button
                className="btn btn-ghost btn-sm"
                disabled={scanState === 'running'}
                onClick={() => { setManualModules([]); setAutoModules([]); setDependencyNotice(null); }}
                style={{ fontSize: 11, padding: '4px 10px', color: 'var(--accent-red)', border: '1px solid rgba(239,68,68,0.2)' }}
              >
                Clear all
              </button>
            )}
          </div>

          {/* Dependency notice */}
          {dependencyNotice && (
            <div style={{
              marginBottom: 12,
              padding: '10px 14px',
              borderRadius: 8,
              border: '1px solid rgba(0,212,170,0.2)',
              background: 'rgba(0,212,170,0.06)',
              fontSize: 12, lineHeight: 1.6,
              display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12,
            }}>
              <div>
                <strong style={{ color: 'var(--accent)' }}>Auto-added dependencies:</strong>{' '}
                <span style={{ color: 'var(--text-primary)' }}>{dependencyNotice.addedNames.join(', ')}</span>
                {dependencyNotice.trigger && (
                  <><br /><span style={{ color: 'var(--text-dim)' }}>Required inputs for <strong style={{ color: 'var(--text-secondary)' }}>{dependencyNotice.trigger}</strong>.</span></>
                )}
                <br />
                <span style={{ color: 'var(--text-dim)', fontSize: 11 }}>
                  These show a lock icon. Click any to pin it as a manual selection.
                </span>
              </div>
              <button
                onClick={dismissAllAuto}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-dim)', padding: '2px 4px', lineHeight: 1, flexShrink: 0, fontSize: 16 }}
                title="Dismiss notice"
              >×</button>
            </div>
          )}

          <ModuleSelector
            selected={resolvedModules}
            manuallySelected={manualModules}
            onChange={(nextManual, meta) => applyModuleSelection(nextManual, meta?.trigger || null)}
            disabled={scanState === 'running'}
          />
        </div>
      )}

      {/* ────────────────── Configuration Card ────────────────── */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title" style={{ marginBottom: 20 }}>Configuration</div>

        {/* Row 1: Core scan parameters */}
        <div style={{ marginBottom: 6 }}>
          <div style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
            color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: 10,
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <Cpu size={11} />
            Scan Parameters
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            <div className="input-group" style={{ marginBottom: 0 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <Cpu size={11} style={{ opacity: 0.5 }} /> Threads
              </label>
              <input className="input" type="number" min="1" max="500" value={threads}
                onChange={inputNum(setThreads, 1, 500)} disabled={scanState === 'running'} />
            </div>
            <div className="input-group" style={{ marginBottom: 0 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <Gauge size={11} style={{ opacity: 0.5 }} /> Rate Limit (req/s)
              </label>
              <input className="input" type="number" min="1" max="10000" value={rateLimit}
                onChange={inputNum(setRateLimit, 1, 10000)} disabled={scanState === 'running'} />
            </div>
            <div className="input-group" style={{ marginBottom: 0 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <Clock size={11} style={{ opacity: 0.5 }} /> Timeout (seconds)
              </label>
              <input className="input" type="number" min="10" max="7200" value={timeout}
                onChange={inputNum(setTimeout_, 10, 7200)} disabled={scanState === 'running'} />
            </div>
          </div>
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: 'var(--border)', margin: '18px 0' }} />

        {/* Row 2: Detection settings */}
        <div style={{ marginBottom: 6 }}>
          <div style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
            color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: 10,
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <ShieldAlert size={11} />
            Detection Settings
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
            <div className="input-group" style={{ marginBottom: 0 }}>
              <label>Nuclei Severity</label>
              <select className="input" value={severity} onChange={e => setSeverity(e.target.value)} disabled={scanState === 'running'}>
                <option value="low,medium,high,critical">All (Low → Critical)</option>
                <option value="medium,high,critical">Medium+</option>
                <option value="high,critical">High + Critical</option>
                <option value="critical">Critical only</option>
              </select>
            </div>
            <div className="input-group" style={{ marginBottom: 0 }}>
              <label>Stealth Jitter</label>
              <div
                className="toggle-row"
                onClick={() => { if (scanState !== 'running') setJitter(!jitter); }}
                style={{
                  height: 42,
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '0 14px',
                  border: jitter ? '1px solid rgba(0,212,170,0.35)' : '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  background: jitter ? 'rgba(0,212,170,0.04)' : 'rgba(255,255,255,0.01)',
                  boxShadow: jitter ? '0 0 14px rgba(0,212,170,0.08)' : 'none',
                  transition: 'all 0.25s ease',
                  cursor: scanState === 'running' ? 'not-allowed' : 'pointer',
                  boxSizing: 'border-box',
                }}
              >
                <span style={{
                  fontSize: 12, fontWeight: 600,
                  color: jitter ? 'var(--accent)' : 'var(--text-dim)',
                  transition: 'color 0.25s',
                }}>
                  {jitter ? 'ON' : 'OFF'}
                </span>
                <div className={`toggle ${jitter ? 'on' : ''}`} style={{ margin: 0 }}>
                  <div className="toggle-knob" />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: 'var(--border)', margin: '18px 0' }} />

        {/* Row 3: SQLMap — collapsible */}
        <div>
          <button
            type="button"
            onClick={() => setSqlOpen(o => !o)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8, width: '100%',
              background: 'none', border: 'none', cursor: 'pointer',
              padding: 0, marginBottom: sqlOpen ? 12 : 0,
            }}
          >
            <div style={{
              fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
              color: 'var(--text-dim)', textTransform: 'uppercase',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              {sqlOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
              SQLMap Injection Parameters
            </div>
            {!sqlOpen && (
              <span style={{
                fontSize: 10, color: 'var(--text-dim)', marginLeft: 4,
                background: 'rgba(255,255,255,0.04)', padding: '2px 8px', borderRadius: 4,
              }}>
                Level {sqlmapLevel} · Risk {sqlmapRisk} · {sqlmapThreads}T
              </span>
            )}
          </button>

          {sqlOpen && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              <div className="input-group" style={{ marginBottom: 0 }}>
                <label>Level <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}>(1–5)</span></label>
                <input className="input" type="number" min="1" max="5" value={sqlmapLevel}
                  onChange={inputNum(setSqlmapLevel, 1, 5)} disabled={scanState === 'running'} />
              </div>
              <div className="input-group" style={{ marginBottom: 0 }}>
                <label>Risk <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}>(1–3)</span></label>
                <input className="input" type="number" min="1" max="3" value={sqlmapRisk}
                  onChange={inputNum(setSqlmapRisk, 1, 3)} disabled={scanState === 'running'} />
              </div>
              <div className="input-group" style={{ marginBottom: 0 }}>
                <label>Threads <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}>(max 10)</span></label>
                <input className="input" type="number" min="1" max="10" value={sqlmapThreads}
                  onChange={inputNum(setSqlmapThreads, 1, 10)} disabled={scanState === 'running'} />
              </div>
            </div>
          )}
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: 'var(--border)', margin: '18px 0' }} />

        {/* Optimization Presets */}
        <div>
          <div style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
            color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: 10,
          }}>
            Optimization Presets
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            {[
              {
                key: 'kali', label: 'Kali Native', Icon: ShieldAlert,
                fg: '#B975FF', bg: 'rgba(168,85,247,0.06)', border: 'rgba(168,85,247,0.15)',
                bgHov: 'rgba(168,85,247,0.14)', borderHov: 'rgba(168,85,247,0.35)',
              },
              {
                key: 'fast', label: 'High Performance', Icon: Flame,
                fg: 'var(--accent-green)', bg: 'rgba(16,185,129,0.06)', border: 'rgba(16,185,129,0.15)',
                bgHov: 'rgba(16,185,129,0.14)', borderHov: 'rgba(16,185,129,0.35)',
              },
              {
                key: 'stealth', label: 'Stealth Ops', Icon: EyeOff,
                fg: 'var(--accent-amber)', bg: 'rgba(245,158,11,0.06)', border: 'rgba(245,158,11,0.15)',
                bgHov: 'rgba(245,158,11,0.14)', borderHov: 'rgba(245,158,11,0.35)',
              },
            ].map(({ key, label, Icon, fg, bg, border, bgHov, borderHov }) => (
              <button
                key={key}
                type="button"
                className="btn btn-ghost btn-sm"
                disabled={scanState === 'running'}
                onClick={() => applyPreset(key)}
                style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 6, borderRadius: 6, background: bg, border: `1px solid ${border}`, color: fg, transition: 'all 0.2s' }}
                onMouseEnter={e => { e.currentTarget.style.background = bgHov; e.currentTarget.style.borderColor = borderHov; e.currentTarget.style.boxShadow = `0 0 12px ${bg}`; }}
                onMouseLeave={e => { e.currentTarget.style.background = bg; e.currentTarget.style.borderColor = border; e.currentTarget.style.boxShadow = 'none'; }}
              >
                <Icon size={12} /> {label}
              </button>
            ))}

            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={scanState === 'running'}
              onClick={resetToDefaults}
              style={{ marginLeft: 'auto', fontSize: 11, display: 'flex', alignItems: 'center', gap: 6, borderRadius: 6, background: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.15)', color: 'var(--accent-red)', transition: 'all 0.2s' }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(239,68,68,0.12)'; e.currentTarget.style.borderColor = 'rgba(239,68,68,0.35)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'rgba(239,68,68,0.04)'; e.currentTarget.style.borderColor = 'rgba(239,68,68,0.15)'; }}
            >
              <RotateCcw size={11} /> Reset to Defaults
            </button>
          </div>
        </div>
      </div>
      {/* ───────────────────────────────────────────── */}

      {error && (
        <div style={{ color: 'var(--accent-red)', fontSize: 13, marginBottom: 12, padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 6 }}>
          {error}
        </div>
      )}

      <button
        className="btn btn-primary"
        disabled={!canStart || scanState === 'running'}
        onClick={() => setShowConfirm(true)}
        style={{ width: '100%', padding: '14px 20px', fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
      >
        <Play size={16} />
        {scanState === 'running' ? 'Scan in Progress…' : 'Start Scan'}
      </button>

      {/* ── Confirmation Modal ── */}
      {showConfirm && (
        <div className="overlay" onClick={() => setShowConfirm(false)}>
          <div className="dialog" onClick={e => e.stopPropagation()}>
            <h3>Confirm Scan Launch</h3>
            <p>
              You are about to launch a <strong>fresh scan</strong> for{' '}
              <strong style={{ color: 'var(--accent)' }}>{domain}</strong> using{' '}
              <strong>{SCAN_MODES.find(m => m.id === mode)?.name}</strong> mode.
              {mode === 'custom' && ` (${resolvedModules.length} modules)`}
            </p>
            <p style={{ marginTop: 8, padding: '8px 12px', borderRadius: 6, background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', fontSize: 12, color: 'var(--accent-amber)', lineHeight: 1.6 }}>
              ⚠️ Any existing <code>output-{domain}/</code> data will be automatically backed
              up to <code>backup-{domain}/</code> before the scan begins — nothing is deleted.
            </p>
            <p style={{ marginTop: 10, fontSize: 12, color: 'var(--text-dim)' }}>
              Ensure you have explicit authorization to scan this target.
            </p>
            <div className="dialog-actions">
              <button className="btn btn-ghost" onClick={() => setShowConfirm(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleStart}
                style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Play size={14} /> Launch Scan
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
