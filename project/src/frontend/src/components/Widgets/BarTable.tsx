import { useState, useEffect } from 'react';
import { apiFetch } from '../../api';
import type { WidgetConfig, BarTableData } from '../../types';
import styles from './BarTable.module.css';

interface BarTableProps {
  config: WidgetConfig;
  onAction?: (endpoint: string) => void;
}

export function BarTable({ config, onAction }: BarTableProps) {
  const [data, setData] = useState<BarTableData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    apiFetch<BarTableData | { data: BarTableData | null }>(config.endpoint)
      .then(d => {
        const payload = (d && 'headers' in d) ? (d as BarTableData) : ((d as { data: BarTableData | null }).data ?? null);
        setData(payload);
        setError(null);
      })
      .catch(e => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [config.endpoint]);

  if (loading) return <div className={styles.loading}>Loading…</div>;
  if (error) return <div className={styles.error}>{error}</div>;
  if (!data) return null;
  if (data.rows.length === 0) return <div className={styles.loading}>{config.empty ?? 'No data yet'}</div>;

  const actionEndpoint = data.action?.endpoint ?? config.action?.endpoint;
  const actionLabel = data.action?.label ?? config.action?.label;

  return (
    <div className={styles.wrapper}>
      {(actionLabel && actionEndpoint) && (
        <div className={styles.topBar}>
          <button
            className={styles.actionBtn}
            onClick={() => onAction?.(actionEndpoint)}
          >
            {actionLabel}
          </button>
        </div>
      )}
      <table className={styles.table}>
        <thead>
          <tr>
            {data.headers.map((h, i) => (
              <th key={i} className={styles.th}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, ri) => (
            <tr key={ri} className={styles.tr}>
              {row.cells.map((cell, ci) => (
                <td key={ci} className={styles.td}>{cell}</td>
              ))}
              {row.bar && (
                <td className={styles.td}>
                  <div className={styles.barTrack}>
                    <div
                      className={`${styles.barFill} ${row.bar.warn ? styles.barWarn : ''}`}
                      style={{ width: `${Math.min(100, (row.bar.value / row.bar.max) * 100)}%` }}
                    />
                  </div>
                  <span className={styles.barLabel}>{row.bar.value.toFixed(1)}%</span>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
