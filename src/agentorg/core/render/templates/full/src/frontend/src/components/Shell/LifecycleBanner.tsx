import { useCallback, useEffect, useState } from 'react';
import { apiFetch, apiPost } from '../../api';
import type { LifecycleInfo } from '../../types';
import styles from '../Views/OpsView.module.css';

const ACTIONS: Record<string, { to: string; label: string }[]> = {
  draft: [{ to: 'trial', label: 'Start trial' }],
  trial: [{ to: 'active', label: 'Promote to active' }, { to: 'paused', label: 'Pause' }],
  active: [{ to: 'paused', label: 'Pause' }],
  paused: [{ to: 'active', label: 'Resume' }],
  retired: [],
};

export function LifecycleBanner({ actor }: { actor: string }) {
  const [info, setInfo] = useState<LifecycleInfo | null>(null);
  const load = useCallback(() => { apiFetch<LifecycleInfo>('/api/v1/lifecycle').then(setInfo).catch(() => setInfo(null)); }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [load]);

  if (!info) return null;

  async function move(to: string) {
    const reason = window.prompt(`Why move the org to ${to}?`);
    if (!reason) return;
    await apiPost('/api/v1/lifecycle', { to, actor, reason });
    load();
  }

  const actions = [...(ACTIONS[info.state] ?? []), ...(info.state === 'retired' ? [] : [{ to: 'retired', label: 'Retire' }])];
  return (
    <div className={styles.banner}>
      <span className={styles.bannerState}>{info.state}</span>
      <span className={styles.bannerReason}>{info.reason}</span>
      {actions.map(action => (
        <button key={action.to} className={styles.button} onClick={() => void move(action.to)}>{action.label}</button>
      ))}
    </div>
  );
}
