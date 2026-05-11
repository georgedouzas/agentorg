import { useEffect } from 'react';
import styles from './Panel.module.css';

interface PanelProps {
  open: boolean;
  title: string;
  sub?: string;
  onClose: () => void;
  children: React.ReactNode;
}

export function Panel({ open, title, sub, onClose, children }: PanelProps) {
  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  return (
    <>
      {open && (
        <div className={styles.backdrop} onClick={onClose} />
      )}
      <div className={`${styles.panel} ${open ? styles.panelOpen : ''}`}>
        <div className={styles.header}>
          <div className={styles.headerText}>
            <span className={styles.title}>{title}</span>
            {sub && <span className={styles.sub}>{sub}</span>}
          </div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close panel">
            ×
          </button>
        </div>
        <div className={styles.body}>
          {children}
        </div>
      </div>
    </>
  );
}
