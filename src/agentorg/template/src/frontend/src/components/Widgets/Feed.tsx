import { useState, useEffect } from 'react';
import { apiFetch } from '../../api';
import type { WidgetConfig, FeedItem } from '../../types';
import styles from './Feed.module.css';

interface FeedProps {
  config: WidgetConfig;
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

export function Feed({ config }: FeedProps) {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    apiFetch<FeedItem[] | { data: FeedItem[] | null }>(config.endpoint)
      .then(d => {
        const list = Array.isArray(d) ? d : (d.data ?? []);
        setItems(list);
        setError(null);
      })
      .catch(e => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [config.endpoint]);

  if (loading) return <div className={styles.loading}>Loading…</div>;
  if (error) return <div className={styles.error}>{error}</div>;
  if (items.length === 0) return <div className={styles.empty}>{config.empty ?? 'No items yet'}</div>;

  return (
    <div className={styles.feed}>
      {items.map((item, i) => (
        <div key={i} className={styles.item}>
          <div className={styles.itemLeft}>
            <div className={styles.itemTitle}>{item.title}</div>
            {item.sub && <div className={styles.itemSub}>{item.sub}</div>}
          </div>
          <div className={styles.itemRight}>
            {item.tag && <span className={styles.tag}>{item.tag}</span>}
            <span className={styles.date}>{formatDate(item.date)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
