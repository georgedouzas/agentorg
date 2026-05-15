import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { marked } from 'marked';
import { ResetModal } from './ResetModal';
import type { SetupStatus, SetupStep } from '../../hooks/useSetupStatus';
import styles from './SettingsView.module.css';

function DoneStep({ step }: { step: SetupStep }) {
  return (
    <li className={styles.stepDone}>
      <span className={styles.checkmark}>✓</span>
      <span className={styles.stepTitle}>{step.title}</span>
    </li>
  );
}

function PendingStep({ step, onClick }: { step: SetupStep; onClick: () => void }) {
  return (
    <li>
      <button type="button" className={styles.stepPending} onClick={onClick}>
        <span className={styles.bullet}>○</span>
        <span className={styles.stepTitle}>{step.title}</span>
        <span className={styles.chevron}>›</span>
      </button>
    </li>
  );
}

function StepDetailModal({ step, onClose }: { step: SetupStep; onClose: () => void }) {
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, []);

  return createPortal(
    <div className={styles.modalBackdrop} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className={styles.modalHeader}>
          <h2 className={styles.modalTitle}>{step.title}</h2>
          <button className={styles.modalCloseBtn} onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className={styles.modalBody}>
          {step.missing_vars && step.missing_vars.length > 0 && (
            <div className={styles.detailRow}>
              <h3 className={styles.detailLabel}>Missing variables</h3>
              <div className={styles.missingVars}>
                {step.missing_vars.map((v, i) => (
                  <span key={v}>{i > 0 && ', '}<code>{v}</code></span>
                ))}
              </div>
            </div>
          )}
          <div className={styles.detailRow}>
            <h3 className={styles.detailLabel}>Instructions</h3>
            <div className="md" dangerouslySetInnerHTML={{ __html: marked.parse(step.description) as string }} />
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

interface SettingsViewProps {
  orgName: string;
  setupStatus: SetupStatus | null;
}

export function SettingsView({ orgName, setupStatus }: SettingsViewProps) {
  const [resetOpen, setResetOpen] = useState(false);
  const [openStep, setOpenStep] = useState<SetupStep | null>(null);

  const done = setupStatus?.steps.filter(s => s.completed === true) ?? [];
  const pending = setupStatus?.steps.filter(s => s.completed !== true) ?? [];

  return (
    <div className={styles.view}>
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>
          Setup
          {pending.length > 0 && <span className={styles.dot} aria-hidden />}
        </h2>
        {(!setupStatus || setupStatus.steps.length === 0) && (
          <p className={styles.muted}>No setup steps configured</p>
        )}
        {done.length > 0 && (
          <div className={styles.subSection}>
            <h3 className={styles.subTitle}>Done</h3>
            <ul className={styles.stepList}>
              {done.map(s => <DoneStep key={s.id} step={s} />)}
            </ul>
          </div>
        )}
        {setupStatus && setupStatus.steps.length > 0 && (
          <div className={styles.subSection}>
            <h3 className={styles.subTitle}>Remaining</h3>
            {pending.length === 0 ? (
              <p className={styles.muted}>Nothing pending</p>
            ) : (
              <ul className={styles.stepList}>
                {pending.map(s => <PendingStep key={s.id} step={s} onClick={() => setOpenStep(s)} />)}
              </ul>
            )}
          </div>
        )}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Reset</h2>
        <p className={styles.muted}>
          Wipe all knowledge, agent history, and parameters.
        </p>
        <button className={styles.dangerBtn} onClick={() => setResetOpen(true)}>
          Reset organisation
        </button>
      </section>

      {resetOpen && <ResetModal orgName={orgName} onClose={() => setResetOpen(false)} />}
      {openStep && <StepDetailModal step={openStep} onClose={() => setOpenStep(null)} />}
    </div>
  );
}
