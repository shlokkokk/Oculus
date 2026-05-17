import { useState, useEffect } from 'react';
import { Eye, Crosshair, Radio, FolderOpen, FileText, Wrench, History, Server } from 'lucide-react';
import { VIEWS } from '../utils/constants';
import { api } from '../api/client';

function OculusLogo({ size = 20 }) {
  return (
    <>
      <svg width="0" height="0" style={{ position: 'absolute' }}>
        <defs>
          <linearGradient id="logo-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#00D4AA"/>
            <stop offset="100%" stopColor="#3B82F6"/>
          </linearGradient>
        </defs>
      </svg>
      <Eye size={size} stroke="url(#logo-gradient)" strokeWidth={2} />
    </>
  );
}

const NAV_ITEMS = [
  { id: VIEWS.SCAN, label: 'New Scan', icon: Crosshair, section: 'Operations' },
  { id: VIEWS.LIVE, label: 'Live Output', icon: Radio, section: 'Operations' },
  { id: VIEWS.RESULTS, label: 'Results', icon: FolderOpen, section: 'Data' },
  { id: VIEWS.REPORTS, label: 'Reports', icon: FileText, section: 'Data' },
  { id: VIEWS.TOOLS, label: 'Tool Status', icon: Wrench, section: 'System' },
  { id: VIEWS.HISTORY, label: 'Scan History', icon: History, section: 'System' },
];

export default function Sidebar({ activeView, onNavigate }) {
  let lastSection = '';
  const [apiOnline, setApiOnline] = useState(true);

  useEffect(() => {
    let active = true;
    const checkHealth = async () => {
      try {
        await api.health();
        if (active) setApiOnline(true);
      } catch (err) {
        if (active) setApiOnline(false);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 3000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <aside className="sidebar" style={{ display: 'flex', flexDirection: 'column' }}>
      <div className="sidebar-brand">
        <div className="sidebar-brand-icon">
          <OculusLogo size={20} />
        </div>
        <div>
          <h1>OCULUS</h1>
          <span style={{ fontSize: '9px', letterSpacing: '0.8px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-dim)', display: 'block', marginTop: '2px' }}>Offensive Operations</span>
        </div>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => {
          const showSection = item.section !== lastSection;
          lastSection = item.section;
          const Icon = item.icon;
          return (
            <div key={item.id}>
              {showSection && <div className="sidebar-section-label">{item.section}</div>}
              <div
                className={`nav-item ${activeView === item.id ? 'active' : ''}`}
                onClick={() => onNavigate(item.id)}
              >
                <Icon size={18} />
                {item.label}
              </div>
            </div>
          );
        })}
      </nav>

      <div style={{ marginTop: 'auto', padding: '16px', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.8px', display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Server size={11} /> System Status
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: apiOnline ? 'var(--accent-green)' : 'var(--accent-red)',
              boxShadow: apiOnline ? '0 0 8px var(--accent-green)' : '0 0 8px var(--accent-red)',
              display: 'inline-block',
              animation: 'pulse-dot 2s infinite ease-in-out'
            }} />
            <span style={{ fontSize: '10px', fontWeight: 700, color: apiOnline ? 'var(--accent-green)' : 'var(--accent-red)', fontFamily: 'var(--font-mono)', letterSpacing: '0.5px' }}>
              {apiOnline ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}
