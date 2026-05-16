import { Crosshair, ScanLine, Radio, FolderOpen, FileText, Wrench, History } from 'lucide-react';
import { VIEWS } from '../utils/constants';

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
          <ScanLine size={18} color="#0B0E14" />
        </div>
        <div>
          <h1>OCULUS</h1>
          <span>Recon Framework</span>
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
