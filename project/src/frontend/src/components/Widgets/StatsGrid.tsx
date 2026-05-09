import { useState, useEffect } from 'react';
import { apiFetch } from '../../api';
import type { WidgetConfig, StatItem } from '../../types';
import styles from './StatsGrid.module.css';

interface StatsGridProps {
  config: WidgetConfig;
}

export function StatsGrid({ config }: StatsGridProps) {
  const [items, setItems] = useState<StatItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    apiFetch<StatItem[] | { data: StatItem[] | null }>(config.endpoint)
      .then(d => {
        const items = Array.isArray(d) ? d : (d.data ?? []);
        setItems(items);
        setError(null);
      })
      .catch(e => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [config.endpoint]);

  if (loading) return <div className={styles.loading}>Loading…</div>;
  if (error) return <div className={styles.error}>{error}</div>;
  if (items.length === 0) return <div className={styles.loading}>{config.empty ?? 'No data yet'}</div>;

  return (
    <div className={styles.grid}>
      {items.map((item, i) => (
        <div key={i} className={styles.card}>
          <div className={styles.label}>{item.label}</div>
          <div className={`${styles.value} ${item.trend === 'pos' ? styles.pos : item.trend === 'neg' ? styles.neg : ''}`}>
            {item.value}
          </div>
          {item.sub && <div className={styles.sub}>{item.sub}</div>}
        </div>
      ))}
    </div>
  );
}
