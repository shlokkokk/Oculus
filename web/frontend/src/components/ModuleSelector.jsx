import { Check } from 'lucide-react';
import { MODULES, PHASES, normalizeModuleOrder } from '../utils/constants';

export default function ModuleSelector({ selected, onChange, disabled }) {
  const toggle = (id) => {
    if (disabled) return;
    const next = selected.includes(id) ? selected.filter(m => m !== id) : [...selected, id];
    onChange(normalizeModuleOrder(next), { source: 'toggle', trigger: id });
  };

  const selectPhase = (phase) => {
    if (disabled) return;
    const phaseModules = MODULES.filter(m => m.phase === phase).map(m => m.id);
    const allSelected = phaseModules.every(id => selected.includes(id));
    if (allSelected) {
      onChange(normalizeModuleOrder(selected.filter(id => !phaseModules.includes(id))), {
        source: 'phase',
        trigger: null,
      });
    } else {
      onChange(normalizeModuleOrder([...selected, ...phaseModules]), {
        source: 'phase',
        trigger: null,
      });
    }
  };

  const phases = Object.entries(PHASES);

  return (
    <div>
      {phases.map(([phaseNum, phase]) => {
        const phaseModules = MODULES.filter(m => m.phase === Number(phaseNum));
        const allSel = phaseModules.every(m => selected.includes(m.id));
        return (
          <div key={phaseNum}>
            <div className="phase-header" onClick={() => selectPhase(Number(phaseNum))} style={{ cursor: 'pointer' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: phase.color, display: 'inline-block' }} />
              Phase {phaseNum}: {phase.name}
              <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-dim)' }}>
                {allSel ? 'Deselect all' : 'Select all'}
              </span>
            </div>
            <div className="module-grid">
              {phaseModules.map(mod => {
                const isSel = selected.includes(mod.id);
                return (
                  <div
                    key={mod.id}
                    className={`module-card ${isSel ? 'selected' : ''} ${disabled ? 'disabled' : ''}`}
                    onClick={() => toggle(mod.id)}
                  >
                    <div className="module-check">
                      {isSel && <Check size={12} />}
                    </div>
                    <div className="module-info">
                      <div className="module-name">{mod.name}</div>
                      <div className="module-tool">{mod.tool}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
