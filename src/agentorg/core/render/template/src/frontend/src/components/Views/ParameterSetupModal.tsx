import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { apiPost } from '../../api';
import type { PrincipleParameter } from '../../types';
import styles from './ResetModal.module.css';

interface ParameterSetupModalProps {
  parameters: PrincipleParameter[];
  onConfigured: () => void;
}

export function ParameterSetupModal({ parameters, onConfigured }: ParameterSetupModalProps) {
  const [values, setValues] = useState<Record<string, string | number | boolean>>(() => {
    const init: Record<string, string | number | boolean> = {};
    for (const p of parameters) init[p.name] = p.default;
    return init;
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, []);

  function setVal(name: string, raw: string, type: string) {
    let v: string | number = raw;
    if (type === 'int') v = parseInt(raw, 10);
    else if (type === 'float') v = parseFloat(raw);
    setValues(prev => ({ ...prev, [name]: Number.isNaN(v) ? raw : v }));
  }

  function resetOne(p: PrincipleParameter) {
    setValues(prev => ({ ...prev, [p.name]: p.default }));
  }

  async function submit() {
    setSubmitting(true);
    try {
      await apiPost('/api/v1/state', values);
      onConfigured();
    } catch (e) {
      window.alert('Setup failed: ' + (e as Error).message);
      setSubmitting(false);
    }
  }

  return createPortal(
    <div className={styles.backdrop}>
      <div className={styles.modal} role="dialog" aria-modal="true">
        <div className={styles.header}>
          <h2 className={styles.title}>Configure organisation</h2>
        </div>
        <p className={styles.sub}>
          Review and adjust the starting parameters before activating your organisation.
        </p>
        <div className={styles.paramList}>
          {(() => {
            const groups = new Map<string, PrincipleParameter[]>();
            for (const p of parameters) {
              const g = p.group ?? '';
              if (!groups.has(g)) groups.set(g, []);
              groups.get(g)!.push(p);
            }
            return Array.from(groups.entries()).map(([group, params]) => (
              <div key={group || 'default'}>
                {group && <div className={styles.groupLabel}>{group}</div>}
                {params.map(p => {
                  const isInt = p.type === 'int';
                  const isNumber = isInt || p.type === 'float';
                  const isModified = values[p.name] !== p.default;
                  return (
                    <div key={p.name} className={styles.row}>
                      <label className={styles.label} htmlFor={`s-${p.name}`}>
                        {p.label || p.name}
                        {p.unit && <span className={styles.unit}>{p.unit}</span>}
                      </label>
                      <div className={styles.inputGroup}>
                        <input
                          id={`s-${p.name}`}
                          className={styles.input}
                          type={isNumber ? 'number' : 'text'}
                          step={isInt ? 1 : 'any'}
                          value={values[p.name] as string | number}
                          onChange={e => setVal(p.name, e.target.value, p.type)}
                        />
                        <button
                          type="button"
                          className={styles.revertBtn}
                          onClick={() => resetOne(p)}
                          disabled={!isModified}
                          title="Revert to default"
                        >↺</button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ));
          })()}
        </div>
        <div className={styles.actions}>
          <button className={styles.confirmBtn} onClick={submit} disabled={submitting}>
            {submitting ? 'Activating…' : 'Activate'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
