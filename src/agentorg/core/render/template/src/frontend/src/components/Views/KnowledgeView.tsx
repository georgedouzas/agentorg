import { useState, useEffect } from 'react';
import { marked } from 'marked';
import { apiFetch } from '../../api';
import type { AppConfig, AgentGroup } from '../../types';
import styles from './KnowledgeView.module.css';

interface KnowledgeItem {
  name: string;
  type: string;
  content: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
}

function formatDate(iso?: string): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const yy = String(d.getFullYear() % 100).padStart(2, '0');
    return `${dd}/${mm}/${yy}`;
  } catch { return ''; }
}

function formatAgentId(id: string): string {
  return id.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function extractTitle(content: string, fallback: string): string {
  const m = content.match(/^#\s+(.+?)\s*$/m);
  return m ? m[1] : fallback;
}

function stripFirstHeading(content: string): string {
  return content.replace(/^#\s+.+?\s*$/m, '').trimStart();
}

function extractDescription(content: string): string {
  const after = stripFirstHeading(content);
  return (after.split(/\n##\s+/)[0] ?? '').trim();
}

interface FilterBarProps {
  searchValue: string;
  onSearch: (v: string) => void;
  agentGroups: AgentGroup[];
  selectedAgent: string;
  onAgent: (v: string) => void;
  searchPlaceholder: string;
  agentIcons: Record<string, string>;
}

function SearchIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

function PeopleIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="8.5" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

function FilterBar({
  searchValue, onSearch, agentGroups, selectedAgent, onAgent, searchPlaceholder, agentIcons,
}: FilterBarProps) {
  return (
    <div className={styles.filterBar}>
      <div className={styles.searchWrap}>
        <span className={styles.inputIcon}><SearchIcon /></span>
        <input
          className={styles.searchInput}
          type="text"
          placeholder={searchPlaceholder}
          value={searchValue}
          onChange={e => onSearch(e.target.value)}
        />
      </div>
      <div className={styles.searchWrap}>
        <span className={styles.inputIcon}><PeopleIcon /></span>
        <select
          className={styles.agentSelect}
          value={selectedAgent}
          onChange={e => onAgent(e.target.value)}
        >
          <option value="">All agents</option>
          {agentGroups.map(group => (
            <optgroup key={group.label} label={group.label}>
              {group.ids.map(a => {
                const icon = agentIcons[a] ?? '🤖';
                return (
                  <option key={a} value={a}>{icon}  {formatAgentId(a)}</option>
                );
              })}
            </optgroup>
          ))}
        </select>
      </div>
    </div>
  );
}

interface ThumbProps {
  title: string;
  description?: string;
  agent?: string;
  date?: string;
  onOpen: () => void;
}

function MetaBadge({ label, value }: { label: string; value: string }) {
  return (
    <span className="badge">
      <span className="badge-label">{label}</span>
      <span className="badge-value">{value}</span>
    </span>
  );
}

function Thumbnail({ title, description, agent, date, onOpen }: ThumbProps) {
  return (
    <button className={styles.thumb} onClick={onOpen} type="button">
      <div className={styles.thumbTitle}>{title}</div>
      {description && (
        <div
          className={`md ${styles.thumbDescription}`}
          dangerouslySetInnerHTML={{ __html: marked.parse(description) as string }}
        />
      )}
      <div className={styles.thumbMeta}>
        {agent && <MetaBadge label="Agent" value={formatAgentId(agent).toUpperCase()} />}
        {date && <MetaBadge label="Date" value={date} />}
      </div>
    </button>
  );
}

interface DetailModalProps {
  title: string;
  agent?: string;
  date?: string;
  content: string;
  onClose: () => void;
}

function DetailModal({ title, agent, date, content, onClose }: DetailModalProps) {
  return (
    <div className={styles.modalBackdrop} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className={styles.modalHeader}>
          <div className={styles.modalTitle}>{title}</div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className={`md ${styles.modalBody}`} dangerouslySetInnerHTML={{ __html: marked.parse(stripFirstHeading(content)) as string }} />
        <div className={styles.modalFooter}>
          {agent && <MetaBadge label="Agent" value={formatAgentId(agent).toUpperCase()} />}
          {date && <MetaBadge label="Date" value={date} />}
        </div>
      </div>
    </div>
  );
}

export function KnowledgeView({ config }: { config: AppConfig }) {
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [agent, setAgent] = useState('');
  const [open, setOpen] = useState<KnowledgeItem | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    apiFetch<KnowledgeItem[]>('/api/v1/knowledge')
      .then(data => setItems(Array.isArray(data) ? data : []))
      .catch(e => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  const q = filter.trim().toLowerCase();
  const visible = items.filter(r => {
    const a = (r.metadata?.agent_id as string | undefined) ?? '';
    if (agent && a !== agent) return false;
    if (q && !(r.name.toLowerCase().includes(q) || r.content.toLowerCase().includes(q))) return false;
    return true;
  });

  return (
    <div className={styles.view}>
      <FilterBar
        searchValue={filter}
        onSearch={setFilter}
        agentGroups={config.agent_groups ?? []}
        selectedAgent={agent}
        onAgent={setAgent}
        searchPlaceholder="Filter by content…"
        agentIcons={config.agent_icons}
      />

      {error && <div className={styles.error}>{error}</div>}
      {loading && <div className={styles.empty}>Loading…</div>}

      {!loading && !error && items.length === 0 && (
        <div className={styles.empty} dangerouslySetInnerHTML={{ __html: marked.parseInline(config.knowledge_empty) as string }} />
      )}

      {!loading && items.length > 0 && visible.length === 0 && (
        <div className={styles.empty}>No knowledge matches these filters</div>
      )}

      <div className={styles.thumbGrid}>
        {visible.map(r => (
          <Thumbnail
            key={`${r.type}/${r.name}`}
            title={extractTitle(r.content ?? '', r.name)}
            description={extractDescription(r.content ?? '')}
            agent={(r.metadata?.agent_id as string | undefined)}
            date={formatDate(r.created_at)}
            onOpen={() => setOpen(r)}
          />
        ))}
      </div>

      {open && (
        <DetailModal
          title={extractTitle(open.content ?? '', open.name)}
          agent={open.metadata?.agent_id as string | undefined}
          date={formatDate(open.created_at)}
          content={open.content ?? ''}
          onClose={() => setOpen(null)}
        />
      )}
    </div>
  );
}
