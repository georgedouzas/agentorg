import { useState, useRef, useEffect } from 'react';
import styles from './Header.module.css';

// In preview mode (master UI iframe), 'switch user' is meaningless - we auto-log-in as
// 'Preview' and there is no per-user persistence to swap into. Hide the popover entirely.
const PREVIEW_MODE = import.meta.env.VITE_AGENTORG_PREVIEW_MODE === 'true';

interface HeaderProps {
  appName: string;
  appIcon: string;
  appDescription: string;
  displayName: string | null;
  onSwitchUser: () => void;
}

export function Header({ appName, appIcon, appDescription, displayName, onSwitchUser }: HeaderProps) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const initial = displayName ? displayName[0].toUpperCase() : '?';

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  return (
    <header className={styles.header}>
      <div className={styles.left}>
        <span className={styles.icon}>{appIcon}</span>
        <div className={styles.titleBlock}>
          <span className={styles.appName}>{appName}</span>
          <span className={styles.appDesc}>{appDescription}</span>
        </div>
      </div>
      {displayName && !PREVIEW_MODE && (
        <div className={styles.right} ref={wrapRef}>
          <button
            className={styles.avatarBtn}
            onClick={() => setOpen(o => !o)}
            aria-label="Account"
            title={displayName}
          >
            {initial}
          </button>
          {open && (
            <div className={styles.popover}>
              <div className={styles.popoverName}>{displayName}</div>
              <button
                className={styles.popoverItem}
                onClick={() => { setOpen(false); onSwitchUser(); }}
              >
                ⇄  Switch user
              </button>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
