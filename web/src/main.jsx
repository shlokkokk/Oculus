import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity, AlertTriangle, Check, Clipboard, Code2, FileJson, Gauge, Globe2, Layers3,
  Lock, PauseCircle, Play, Radar, Route, Search, Shield, SlidersHorizontal, Sparkles,
  Square, Terminal, Zap
} from 'lucide-react';
import catalog from '../shared/modules.json';
import './styles.css';

const { modules, modes } = catalog;
const phaseIcons = { Discovery: Search, Infrastructure: Radar, Content: Route, Vulnerability: Shield, Exploitation: Zap };

function App() {
  const [domain, setDomain] = useState('example.com');
  const [mode, setMode] = useState('custom');
  const [selected, setSelected] = useState(modes.custom.modules);
  const [threads, setThreads] = useState(50);
  const [timeout, setTimeoutValue] = useState(300);
  const [rateLimit, setRateLimit] = useState(150);
  const [autoConfirm, setAutoConfirm] = useState(true);
  const [jitter, setJitter] = useState(false);
  const [activeScan, setActiveScan] = useState(null);
  const [logs, setLogs] = useState([]);
  const [report, setReport] = useState(null);
  const terminalRef = useRef(null);

  const selectedModules = modules.filter((item) => selected.includes(item.id));
  const grouped = useMemo(() => selectedModules.reduce((acc, item) => {
    acc[item.phase] = [...(acc[item.phase] || []), item];
    return acc;
  }, {}), [selectedModules]);

  const payload = useMemo(() => ({
    domain: domain.trim(),
    mode,
    modules: selected,
    options: { threads, timeout, rate_limit: rateLimit, auto_confirm: autoConfirm, jitter }
  }), [domain, mode, selected, threads, timeout, rateLimit, autoConfirm, jitter]);

  const command = buildCommand(payload);
  const isRunning = activeScan?.status === 'running' || activeScan?.status === 'starting';

  useEffect(() => {
    if (!activeScan?.id) return undefined;
    const events = new EventSource(`/api/scans/${activeScan.id}/events`);
    events.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'log') setLogs((items) => [...items.slice(-700), data.line]);
      if (data.type === 'status') setActiveScan(data.scan);
      if (data.type === 'report') setReport(data.report);
    };
    events.onerror = () => events.close();
    return () => events.close();
  }, [activeScan?.id]);

  useEffect(() => {
    terminalRef.current?.scrollTo({ top: terminalRef.current.scrollHeight });
  }, [logs]);

  function chooseMode(nextMode) {
    setMode(nextMode);
    setSelected(modes[nextMode].modules);
  }

  function toggleModule(id) {
    setMode('custom');
    setSelected((items) => (items.includes(id) ? items.filter((item) => item !== id) : [...items, id]));
  }

  async function startScan() {
    setLogs([]);
    setReport(null);
    const response = await fetch('/api/scans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) {
      setLogs([data.detail || 'Could not start scan.']);
      return;
    }
    setActiveScan(data);
  }

  async function stopScan() {
    if (!activeScan?.id) return;
    await fetch(`/api/scans/${activeScan.id}/stop`, { method: 'POST' });
  }

  async function copy(text) {
    await navigator.clipboard.writeText(text);
  }

  return (
    <main>
      <nav className="topbar">
        <div className="brand">
          <span className="brandMark"><Globe2 size={22} /></span>
          <div><strong>Oculus</strong><small>Web Console</small></div>
        </div>
        <div className="navStats">
          <span><Lock size={14} /> Local runner</span>
          <span><Terminal size={14} /> Existing CLI engine</span>
          <span><Activity size={14} /> {selected.length} modules</span>
        </div>
      </nav>

      <section className="hero">
        <div className="heroCopy">
          <p className="eyebrow"><Sparkles size={15} /> Authorized recon workspace</p>
          <h1>Oculus, with a real web cockpit.</h1>
          <p>Launch scans, stream output, stop jobs, tune config, and review generated artifacts while the Python CLI remains the source of truth.</p>
        </div>
        <div className="heroPanel">
          <label>Target domain</label>
          <div className="targetRow"><Globe2 size={19} /><input value={domain} onChange={(event) => setDomain(event.target.value)} spellCheck="false" /></div>
          <div className="commandBox"><code>{command}</code><button onClick={() => copy(command)} title="Copy command"><Clipboard size={17} /></button></div>
          <div className="runRow">
            <button className="runButton" disabled={isRunning || !domain.trim()} onClick={startScan}><Play size={18} /> Start scan</button>
            <button className="stopButton" disabled={!isRunning} onClick={stopScan}><Square size={17} /> Stop</button>
          </div>
          <p className="guardrail"><AlertTriangle size={15} /> Only scan systems you own or have written permission to test.</p>
        </div>
      </section>

      <section className="workspace">
        <aside className="controlRail">
          <Panel title="Scan Mode" icon={Layers3}>
            <div className="modeList">
              {Object.entries(modes).map(([key, item]) => (
                <button className={mode === key ? 'mode active' : 'mode'} onClick={() => chooseMode(key)} key={key}>
                  <span>{item.label}</span><small>{item.copy}</small>
                </button>
              ))}
            </div>
          </Panel>
          <Panel title="Runtime" icon={SlidersHorizontal}>
            <Range label="Threads" value={threads} min={10} max={120} onChange={setThreads} />
            <Range label="Timeout" value={timeout} min={60} max={900} step={30} onChange={setTimeoutValue} suffix="s" />
            <Range label="Rate limit" value={rateLimit} min={25} max={500} step={25} onChange={setRateLimit} />
            <Toggle label="Skip confirmations" checked={autoConfirm} onChange={setAutoConfirm} />
            <Toggle label="Jitter between tools" checked={jitter} onChange={setJitter} />
          </Panel>
        </aside>

        <section className="planner">
          <div className="sectionHead">
            <div><p className="eyebrow"><Gauge size={15} /> Pipeline planner</p><h2>Choose the surface you want to cover</h2></div>
            <button className="ghostButton" onClick={() => copy(selected.join(','))}><Clipboard size={16} /> Copy modules</button>
          </div>
          <div className="moduleGrid">
            {modules.map((item) => (
              <button key={item.id} className={`moduleCard ${selected.includes(item.id) ? 'selected' : ''} ${item.tone}`} onClick={() => toggleModule(item.id)}>
                <span className="step">{item.step}</span><strong>{item.label}</strong><small>{item.tools}</small><em>{item.output}</em>
                {selected.includes(item.id) && <Check className="check" size={17} />}
              </button>
            ))}
          </div>
        </section>
      </section>

      <section className="opsGrid">
        <Panel title="Live Terminal" icon={Terminal}>
          <div className="scanStatus">
            <span className={`statusDot ${activeScan?.status || 'idle'}`} />
            <b>{activeScan?.status || 'idle'}</b>
            {activeScan?.output_dir && <small>{activeScan.output_dir}</small>}
          </div>
          <pre className="terminal" ref={terminalRef}>{logs.length ? logs.join('\n') : 'Start a scan to stream Oculus output here.'}</pre>
        </Panel>
        <Panel title="Selected Flow" icon={Route}>
          <div className="phaseStack">
            {Object.entries(grouped).map(([phase, items]) => {
              const Icon = phaseIcons[phase];
              return <div className="phase" key={phase}><div className="phaseTitle"><Icon size={17} /> {phase}</div><div className="phaseItems">{items.map((item) => <span key={item.id}>{item.id}</span>)}</div></div>;
            })}
          </div>
        </Panel>
        <Panel title="Report Snapshot" icon={FileJson}>
          <div className="reportCard">
            <Shield size={24} />
            <strong>{report?.finding_count ?? 0}</strong>
            <span>findings detected in the latest generated JSON artifact</span>
          </div>
          {report?.report_html && <a className="reportLink" href={report.report_html} target="_blank" rel="noreferrer">Open HTML report</a>}
          {report?.findings_json && <a className="reportLink" href={report.findings_json} target="_blank" rel="noreferrer">Open findings JSON</a>}
        </Panel>
      </section>
    </main>
  );
}

function buildCommand(scan) {
  const base = [`python3 oculus.py -d ${scan.domain || 'target.com'}`];
  if (scan.mode !== 'custom') base.push(modes[scan.mode].flag);
  else base.push(`--module ${scan.modules.join(',') || 'subdomain,dns,alive'}`);
  if (scan.options.auto_confirm) base.push('--no-confirm');
  if (scan.options.threads !== 50) base.push(`--threads ${scan.options.threads}`);
  if (scan.options.timeout !== 300) base.push(`--timeout ${scan.options.timeout}`);
  if (scan.options.jitter) base.push('--jitter');
  return base.join(' ');
}

function Panel({ title, icon: Icon, children }) {
  return <section className="panel"><h3><Icon size={18} /> {title}</h3>{children}</section>;
}

function Range({ label, value, onChange, min, max, step = 1, suffix = '' }) {
  return <label className="rangeControl"><span>{label}<b>{value}{suffix}</b></span><input type="range" value={value} min={min} max={max} step={step} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}

function Toggle({ label, checked, onChange }) {
  return <button className={checked ? 'toggle on' : 'toggle'} onClick={() => onChange(!checked)}><span>{label}</span><i>{checked ? <Check size={13} /> : <PauseCircle size={13} />}</i></button>;
}

createRoot(document.getElementById('root')).render(<App />);
