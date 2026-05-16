import { Clock } from 'lucide-react';
import { useState, useEffect } from 'react';

function formatElapsed(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function TopBar({ scanState, scanDomain, elapsed }) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <header className="topbar">
      <div className="topbar-left">
        {scanDomain && <span className="domain-display">{scanDomain}</span>}
        {scanState === 'running' && elapsed > 0 && (
          <span style={{ fontSize: 12, color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: 4 }}>
            <Clock size={12} /> {formatElapsed(elapsed)}
          </span>
        )}
      </div>
      <div className="topbar-right">
        <span style={{ fontSize: 12, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
          {time.toLocaleTimeString()}
        </span>
        <div className={`status-badge ${scanState}`}>
          <span className="status-dot" />
          {scanState}
        </div>
      </div>
    </header>
  );
}
