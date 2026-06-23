import { useEffect, useState } from 'react';
import { apiFetch } from '../../api';
import styles from './ActivityStrip.module.css';

interface ActivitySummary {
  summary: string;
  level: 'idle' | 'active' | 'busy';
  count_recent: number;
  latest_at: string | null;
}

interface ActivityStripProps {
  refreshKey?: number;
}

// Always-visible bottom strip carrying a single-sentence pulse of the whole org.
// One sentence is the entire payload by design: this is the heartbeat, not the feed.
// For the full feed the user opens the Knowledge tab.
export function ActivityStrip({ refreshKey = 0 }: ActivityStripProps) {
  const [data, setData] = useState<ActivitySummary | null>(null);

  useEffect(() => {
    apiFetch<ActivitySummary>('/api/v1/activity/summary')
      .then(setData)
      .catch(() => setData({ summary: '', level: 'idle', count_recent: 0, latest_at: null }));
  }, [refreshKey]);

  const level = data?.level ?? 'idle';
  const summary = data?.summary || 'No agent activity yet.';

  return (
    <aside className={styles.strip} aria-label="Org activity summary">
      <span className={`${styles.dot} ${styles[`dot-${level}`]}`} aria-hidden />
      <span className={styles.label}>Activity</span>
      <span className={styles.summary}>{summary}</span>
    </aside>
  );
}
