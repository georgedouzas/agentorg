import { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch, decideApproval } from '../../api';
import type { ApprovalItem, InboxEntry } from '../../types';
import styles from './OpsView.module.css';

function ApprovalCard({ approval, actor, focused, onDecided }: { approval: ApprovalItem; actor: string; focused: boolean; onDecided: () => void }) {
  const [editing, setEditing] = useState(false);
  const [args, setArgs] = useState(JSON.stringify(approval.arguments, null, 2));
  const [comment, setComment] = useState('');
  const [error, setError] = useState('');
  const card = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (focused) card.current?.scrollIntoView({ block: 'center' });
  }, [focused]);

  async function decide(approved: boolean, withEdits: boolean) {
    let edited: Record<string, unknown> | undefined;
    if (withEdits) {
      try { edited = JSON.parse(args) as Record<string, unknown>; } catch { setError('The edited arguments are not valid JSON.'); return; }
    }
    await decideApproval(approval.id, actor, approved, comment, edited);
    onDecided();
  }

  return (
    <div
      className={styles.detail}
      ref={card}
      style={focused ? { outline: '2px solid var(--accent)' } : undefined}
    >
      <div><strong>{approval.tool_name}</strong> · {approval.action_class.replace('_', ' ')} · run {approval.run_id.slice(0, 8)}</div>
      <div className={styles.rowSub}>Approvers: {approval.approvers.join(', ') || 'org admin'}</div>
      {editing
        ? <textarea className={styles.textarea} value={args} onChange={e => setArgs(e.target.value)} />
        : <pre className={styles.pre}>{JSON.stringify(approval.arguments, null, 2)}</pre>}
      <input className={styles.textarea} style={{ minHeight: 0 }} placeholder="Comment (shown to the agent on rejection)" value={comment} onChange={e => setComment(e.target.value)} />
      {error && <div className={styles.rowSub}>{error}</div>}
      <div className={styles.actions}>
        <button className={`${styles.button} ${styles.approve}`} onClick={() => void decide(true, editing)}>{editing ? 'Approve with edits' : 'Approve'}</button>
        {!editing && <button className={styles.button} onClick={() => setEditing(true)}>Edit</button>}
        <button className={`${styles.button} ${styles.reject}`} onClick={() => void decide(false, false)}>Reject</button>
      </div>
    </div>
  );
}

export function InboxView({ actor, focus = null }: { actor: string; focus?: string | null }) {
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [items, setItems] = useState<InboxEntry[]>([]);

  const load = useCallback(() => {
    apiFetch<ApprovalItem[]>('/api/v1/approvals').then(setApprovals).catch(() => setApprovals([]));
    apiFetch<InboxEntry[]>('/api/v1/inbox').then(setItems).catch(() => setItems([]));
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [load]);

  return (
    <div className={styles.view}>
      <h2 className={styles.title}>Approvals</h2>
      <div className={styles.list}>
        {approvals.length === 0 && <div className={styles.empty}>Nothing is waiting for approval.</div>}
        {approvals.map(approval => <ApprovalCard key={approval.id} approval={approval} actor={actor} focused={approval.id === focus} onDecided={load} />)}
      </div>
      <h2 className={styles.title}>Inbox</h2>
      <div className={styles.list}>
        {items.length === 0 && <div className={styles.empty}>No escalations or notifications.</div>}
        {items.map(item => (
          <div key={item.id} className={styles.row}>
            <div className={styles.rowMain}>
              <span className={styles.rowTitle}>{item.reason}</span>
              <span className={styles.rowSub}>{item.kind} · {new Date(item.created_at).toLocaleString()}{item.run_id ? ` · run ${item.run_id.slice(0, 8)}` : ''}</span>
            </div>
            <span className={styles.status}>{item.kind}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
