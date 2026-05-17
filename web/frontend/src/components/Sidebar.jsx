import { Eye, Crosshair, Radio, FolderOpen, FileText, Wrench, History } from 'lucide-react';
import { VIEWS } from '../utils/constants';

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

  return (
    <aside className="sidebar">
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
    </aside>
  );
}
