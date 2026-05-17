import { useRef, useEffect } from 'react';
import { Copy } from 'lucide-react';

function classifyLine(line) {
  const l = line.toLowerCase();
  if (l.includes('[error]') || l.includes('[fatal]') || l.includes('[!]') || l.includes('failed')) return 'error';
  if (l.includes('[✔]') || l.includes('completed') || l.includes('success')) return 'success';
  if (l.includes('[*]') || l.includes('starting') || l.includes('running')) return 'info';
  if (l.includes('[+]') || l.includes('found')) return 'highlight';
  return '';
}

export default function Terminal({ lines, title }) {
  const bodyRef = useRef(null);
  const autoScroll = useRef(true);

  useEffect(() => {
    const el = bodyRef.current;
    if (el && autoScroll.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [lines]);

  const handleScroll = () => {
    const el = bodyRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    autoScroll.current = atBottom;
  };

  const copyAll = () => {
    navigator.clipboard.writeText(lines.join('\n')).catch(() => {});
  };

  return (
    <div className="terminal" style={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minHeight: 0 }}>
      <div className="terminal-header" style={{ flexShrink: 0 }}>
        <div className="terminal-dots">
          <span className="terminal-dot red" />
          <span className="terminal-dot yellow" />
          <span className="terminal-dot green" />
        </div>
        <span className="terminal-title">{title || 'oculus'} — {lines.length} lines</span>
        <button className="btn btn-ghost btn-sm" onClick={copyAll} title="Copy all">
          <Copy size={12} />
        </button>
      </div>
      <div className="terminal-body" ref={bodyRef} onScroll={handleScroll} style={{ flexGrow: 1, height: '100%', maxHeight: 'none', overflowY: 'auto' }}>
        {lines.length === 0 ? (
          <div style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>Waiting for output...</div>
        ) : (
          lines.map((line, i) => (
            <div key={i} className={`terminal-line ${classifyLine(line)}`}>{line}</div>
          ))
        )}
      </div>
    </div>
  );
}
