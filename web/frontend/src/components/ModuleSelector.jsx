import { useState } from 'react';
import { Check, Lock } from 'lucide-react';
import { MODULES, PHASES, normalizeModuleOrder, getAutoReason } from '../utils/constants';

/**
 * ModuleSelector — two-set state model.
 *
 * Props:
 *   selected          (string[]) — full resolved list (manual ∪ auto), used for
 *                                  rendering "selected" border colour.
 *   manuallySelected  (string[]) — only what the user explicitly picked.
 *   onChange(nextManual, meta)   — called with the NEW manual set (not the full
 *                                  resolved set). ScanConfigurator derives auto
 *                                  from this via computeDependencyState().
 *   disabled          (bool)     — locks all interaction during an active scan.
 *
 * Interaction rules:
 *   • Clicking an un-selected module  → adds it to manual.
 *   • Clicking a manually-selected module → removes it from manual.
 *     If nothing else depends on its auto-added deps, those deps are removed too
 *     (handled in ScanConfigurator.applyModuleSelection via computeDependencyState).
 *   • Clicking an auto-added module (lock icon) → promotes it to manual so the
 *     user retains it even if the triggering module is later unchecked.
 *   • Phase header "Select all / Deselect all" operates only on the manual set;
 *     auto-adds are re-derived in ScanConfigurator after every call.
 */
export default function ModuleSelector({ selected = [], manuallySelected = [], onChange, disabled }) {
  const [hoveredAuto, setHoveredAuto] = useState(null);

  const manualSet = new Set(manuallySelected);
  const autoSet   = new Set(selected.filter(id => !manualSet.has(id)));

  const toggle = (id) => {
    if (disabled) return;
    let nextManual;
    if (manualSet.has(id)) {
      // Remove from manual; ScanConfigurator will drop any now-orphaned autos
      nextManual = normalizeModuleOrder(manuallySelected.filter(m => m !== id));
    } else {
      // Add to manual (covers both fresh add and promoting an auto-added module)
      nextManual = normalizeModuleOrder([...manuallySelected, id]);
    }
    onChange(nextManual, { source: 'toggle', trigger: id });
  };

  const selectPhase = (phase) => {
    if (disabled) return;
    const phaseIds = MODULES.filter(m => m.phase === phase).map(m => m.id);
    const allManual = phaseIds.every(id => manualSet.has(id));
    const nextManual = allManual
      ? normalizeModuleOrder(manuallySelected.filter(id => !phaseIds.includes(id)))
      : normalizeModuleOrder([...manuallySelected, ...phaseIds]);
    onChange(nextManual, { source: 'phase', trigger: null });
  };

  return (
    <div>
      {Object.entries(PHASES).map(([phaseNum, phase]) => {
        const phaseModules = MODULES.filter(m => m.phase === Number(phaseNum));
        const allManual    = phaseModules.every(m => manualSet.has(m.id));

        return (
          <div key={phaseNum} style={{ marginBottom: 18 }}>
            {/* Phase Header */}
            <div
              className="phase-header"
              onClick={() => selectPhase(Number(phaseNum))}
              style={{ cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1 }}
            >
              <span style={{
                width: 8, height: 8, borderRadius: '50%',
                background: phase.color, display: 'inline-block', flexShrink: 0,
              }} />
              Phase {phaseNum}: {phase.name}
              <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-dim)', fontWeight: 600 }}>
                {allManual ? 'Deselect all' : 'Select all'}
              </span>
            </div>

            {/* Module Cards */}
            <div className="module-grid">
              {phaseModules.map(mod => {
                const isManual = manualSet.has(mod.id);
                const isAuto   = autoSet.has(mod.id);
                const isSel    = isManual || isAuto;
                const reasons  = isAuto ? getAutoReason(mod.id, manuallySelected) : [];
                const isHovered = hoveredAuto === mod.id;

                return (
                  <div
                    key={mod.id}
                    className={`module-card ${isSel ? 'selected' : ''} ${disabled ? 'disabled' : ''}`}
                    onClick={() => toggle(mod.id)}
                    onMouseEnter={() => isAuto && setHoveredAuto(mod.id)}
                    onMouseLeave={() => isAuto && setHoveredAuto(null)}
                    style={{
                      cursor: disabled ? 'not-allowed' : 'pointer',
                      position: 'relative',
                      // Auto-added modules get a subtler accent glow so they're
                      // visually distinct from manually-selected ones
                      boxShadow: isAuto
                        ? '0 0 0 1px rgba(0,212,170,0.2), inset 0 0 12px rgba(0,212,170,0.04)'
                        : undefined,
                    }}
                  >
                    {/* Check / Lock icon */}
                    <div className="module-check">
                      {isManual && <Check size={12} />}
                      {isAuto   && (
                        <Lock
                          size={10}
                          style={{ color: 'var(--accent)', opacity: 0.75 }}
                        />
                      )}
                    </div>

                    <div className="module-info">
                      <div className="module-name">{mod.name}</div>
                      <div className="module-tool">{mod.tool}</div>
                    </div>

                    {/* AUTO badge */}
                    {isAuto && (
                      <span style={{
                        position: 'absolute', top: 6, right: 6,
                        fontSize: 9, fontWeight: 700, letterSpacing: '0.05em',
                        padding: '2px 5px', borderRadius: 3,
                        background: 'rgba(0,212,170,0.1)',
                        color: 'var(--accent)',
                        border: '1px solid rgba(0,212,170,0.25)',
                        textTransform: 'uppercase',
                        pointerEvents: 'none',
                        transition: 'opacity 0.2s',
                      }}>
                        AUTO
                      </span>
                    )}

                    {/* Tooltip explaining why this module was auto-added */}
                    {isAuto && isHovered && reasons.length > 0 && (
                      <div style={{
                        position: 'absolute', bottom: 'calc(100% + 6px)', left: '50%',
                        transform: 'translateX(-50%)',
                        background: 'var(--bg-secondary)',
                        border: '1px solid var(--accent)',
                        borderRadius: 6,
                        padding: '6px 10px',
                        fontSize: 11, lineHeight: 1.4,
                        color: 'var(--text-primary)',
                        whiteSpace: 'nowrap',
                        zIndex: 50,
                        boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
                        pointerEvents: 'none',
                      }}>
                        <span style={{ color: 'var(--accent)', fontWeight: 600 }}>Required by:</span>{' '}
                        {reasons.join(', ')}
                        <br />
                        <span style={{ color: 'var(--text-dim)', fontSize: 10 }}>
                          Click to pin as manual selection
                        </span>
                      </div>
                    )}
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
