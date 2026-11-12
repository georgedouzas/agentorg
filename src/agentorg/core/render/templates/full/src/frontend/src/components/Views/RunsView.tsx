import { useCallback, useEffect, useState } from 'react';
import { apiFetch, apiPost } from '../../api';
import type { RunDetail, RunSummary } from '../../types';
import styles from './OpsView.module.css';

const STATUSES = ['', 'queued', 'running', 'awaiting_approval', 'succeeded', 'failed', 'cancelled'];
const ACTIVE = ['queued', 'running', 'awaiting_approval'];

function describe(event: Record<string, unknown>): string {
  if (event.type === 'text') return String(event.text ?? '');
  if (event.type === 'tool_call') return `→ ${String(event.name)} ${JSON.stringify(event.input ?? {})}`;
  if (event.type === 'tool_result') return `← ${event.is_error ? 'error: ' : ''}${String(event.text ?? '')}`;
  return `• ${String(event.type)} ${JSON.stringify(event)}`;
}

function RunDetailPane({ runId, onCancelled }: { runId: string; onCancelled: () => void }) {
  const [run, setRun] = useState<RunDetail | null>(null);
  useEffect(() => { apiFetch<RunDetail>(`/api/v1/runs/${runId}`).then(setRun).catch(() => setRun(null)); }, [runId]);
  if (!run) return <div className={styles.empty}>Loading run…</div>;
  return (
    <div className={styles.detail}>
      <div><strong>{run.target}</strong> · {run.trigger_kind}{run.trigger_id ? ` (${run.trigger_id})` : ''} · {run.cost_usd.toFixed(4)} USD</div>
      <pre className={styles.pre}>{run.prompt}</pre>
      {run.transcript.map((event, index) => <pre key={index} className={styles.pre}>{describe(event)}</pre>)}
      {run.children.length > 0 && <div>Delegated: {run.children.map(child => `${child.target} (${child.status})`).join(', ')}</div>}
      {ACTIVE.includes(run.status) && (
        <div className={styles.actions}>
          <button className={`${styles.button} ${styles.reject}`} onClick={() => void apiPost(`/api/v1/runs/${run.id}/cancel`, {}).then(onCancelled)}>
            Cancel run
          </button>
        </div>
      )}
    </div>
  );
}

export function RunsView() {
  const [status, setStatus] = useState('');
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(() => {
    apiFetch<RunSummary[]>(`/api/v1/runs${status ? `?status=${status}` : ''}`).then(setRuns).catch(() => setRuns([]));
  }, [status]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [load]);

  return (
    <div className={styles.view}>
      <h2 className={styles.title}>Runs</h2>
      <div className={styles.filters}>
        {STATUSES.map(value => (
          <button key={value || 'all'} className={`${styles.filter} ${status === value ? styles.filterActive : ''}`} onClick={() => setStatus(value)}>
            {value ? value.replace('_', ' ') : 'all'}
          </button>
        ))}
      </div>
      <div className={styles.list}>
        {runs.length === 0 && <div className={styles.empty}>No runs yet.</div>}
        {runs.map(run => (
          <div key={run.id}>
            <div className={styles.row} onClick={() => setOpen(open === run.id ? null : run.id)}>
              <div className={styles.rowMain}>
                <span className={styles.rowTitle}>{run.target}</span>
                <span className={styles.rowSub}>
                  {run.trigger_kind} · {run.created_at ? new Date(run.created_at).toLocaleString() : ''}
                  {run.failure_reason ? ` · ${run.failure_reason}` : ''}
                </span>
              </div>
              <span className={`${styles.status} ${styles[`status_${run.status}`] ?? ''}`}>{run.status.replace('_', ' ')}</span>
            </div>
            {open === run.id && <RunDetailPane runId={run.id} onCancelled={load} />}
          </div>
        ))}
      </div>
    </div>
  );
}
