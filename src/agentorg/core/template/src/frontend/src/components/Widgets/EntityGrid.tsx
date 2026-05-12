import { useState, useEffect } from 'react';
import { apiFetch } from '../../api';
import type { WidgetConfig, EntityItem } from '../../types';
import styles from './EntityGrid.module.css';

interface EntityGridProps {
  config: WidgetConfig;
  onEntitySelect?: (entityId: string) => void;
  selectedEntityId?: string;
  onItemsChange?: (count: number) => void;
}

export function EntityGrid({ config, onEntitySelect, selectedEntityId, onItemsChange }: EntityGridProps) {
  const [items, setItems] = useState<EntityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const cols = config.cols ?? 2;

  useEffect(() => {
    setLoading(true);
    apiFetch<EntityItem[] | { data: EntityItem[] | null }>(config.endpoint)
      .then(d => {
        const list = Array.isArray(d) ? d : (d.data ?? []);
        setItems(list);
        setError(null);
        onItemsChange?.(list.length);
      })
      .catch(e => { setError((e as Error).message); onItemsChange?.(0); })
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.endpoint]);

  if (loading) return <div className={styles.loading}>Loading…</div>;
  if (error) return <div className={styles.error}>{error}</div>;
  if (items.length === 0) return <div className={styles.loading}>{config.empty ?? 'No items yet'}</div>;

  return (
    <div className={styles.grid} style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
      {items.map(item => (
        <div
          key={item.id}
          className={`${styles.card} ${selectedEntityId === item.id ? styles.cardSelected : ''} ${onEntitySelect ? styles.cardClickable : ''}`}
          onClick={() => onEntitySelect?.(item.id)}
        >
          <div className={styles.cardHeader}>
            <div className={styles.cardTitle}>
              <span className={styles.title}>{item.title}</span>
              {item.subtitle && <span className={styles.subtitle}>{item.subtitle}</span>}
            </div>
            {item.badge && (
              <span className={styles.badge}>{item.badge}</span>
            )}
          </div>
          {item.metrics.length > 0 && (
            <div className={styles.metrics}>
              {item.metrics.map((m, i) => (
                <div key={i} className={styles.metric}>
                  <span className={styles.metricLabel}>{m.label}</span>
                  <span className={`${styles.metricValue} ${m.trend === 'pos' ? styles.pos : m.trend === 'neg' ? styles.neg : ''}`}>
                    {m.value}
                  </span>
                </div>
              ))}
            </div>
          )}
          {item.actions && item.actions.length > 0 && (
            <div className={styles.actions}>
              {item.actions.map((action, i) => (
                <button
                  key={i}
                  className={styles.actionBtn}
                  onClick={e => {
                    e.stopPropagation();
                    // action endpoint handler would be wired by parent
                  }}
                >
                  {action.label}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
