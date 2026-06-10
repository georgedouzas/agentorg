import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { apiPost } from '../../api';
import styles from './ResetModal.module.css';

interface ResetModalProps {
  orgName: string;
  onClose: () => void;
}

export function ResetModal({ orgName, onClose }: ResetModalProps) {
  const [confirmText, setConfirmText] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, []);

  async function submit() {
    setSubmitting(true);
    try {
      await apiPost('/api/v1/parameters/reset', {});
      window.location.reload();
    } catch (e) {
      window.alert('Reset failed: ' + (e as Error).message);
      setSubmitting(false);
    }
  }

  const canConfirm = confirmText.trim().toLowerCase() === orgName.trim().toLowerCase();

  return createPortal(
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className={styles.header}>
          <h2 className={styles.title}>Reset organisation</h2>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close">×</button>
        </div>
        <p className={styles.sub}>
          This deletes all knowledge and agent history, then resets parameters
          to defaults. To confirm, type the organisation name <strong>{orgName}</strong>
        </p>
        <input
          className={styles.confirmInput}
          type="text"
          placeholder={orgName}
          value={confirmText}
          onChange={e => setConfirmText(e.target.value)}
          autoFocus
        />
        <div className={styles.actions}>
          <button className={styles.cancelBtn} onClick={onClose}>Cancel</button>
          <button
            className={styles.resetBtn}
            onClick={submit}
            disabled={!canConfirm || submitting}
          >
            {submitting ? 'Resetting…' : 'Reset'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
