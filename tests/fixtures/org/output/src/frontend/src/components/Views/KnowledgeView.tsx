import { useState, useEffect, useMemo, useRef } from 'react';
import { marked } from 'marked';
import { apiFetch, API_BASE, getUserId } from '../../api';
import type { AppConfig, KnowledgeType, AgentGroup } from '../../types';
import styles from './KnowledgeView.module.css';

interface KnowledgeItem {
  name: string;
  type: string;
  title?: string;
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

function extractTitle(unit: KnowledgeItem): string {
  if (unit.title) return unit.title;
  const m = (unit.content ?? '').match(/^#\s+(.+?)\s*$/m);
  return m ? m[1] : unit.name;
}

function stripFirstHeading(content: string): string {
  return content.replace(/^#\s+.+?\s*$/m, '').trimStart();
}

function extractDescription(content: string): string {
  const after = stripFirstHeading(content);
  return (after.split(/\n##\s+/)[0] ?? '').trim();
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

interface FilterBarProps {
  searchValue: string;
  onSearch: (v: string) => void;
  agentGroups: AgentGroup[];
  selectedAgent: string;
  onAgent: (v: string) => void;
  agentIcons: Record<string, string>;
}

function FilterBar({ searchValue, onSearch, agentGroups, selectedAgent, onAgent, agentIcons }: FilterBarProps) {
  return (
    <div className={styles.filterBar}>
      <div className={styles.searchWrap}>
        <span className={styles.inputIcon}><SearchIcon /></span>
        <input
          className={styles.searchInput}
          type="text"
          placeholder="Search by meaning…"
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
                return <option key={a} value={a}>{icon}  {formatAgentId(a)}</option>;
              })}
            </optgroup>
          ))}
        </select>
      </div>
    </div>
  );
}

function MetaBadge({ label, value }: { label: string; value: string }) {
  return (
    <span className="badge">
      <span className="badge-label">{label}</span>
      <span className="badge-value">{value}</span>
    </span>
  );
}

function Thumbnail({ unit, onOpen }: { unit: KnowledgeItem; onOpen: () => void }) {
  const agent = unit.metadata?.agent_id as string | undefined;
  const date = formatDate(unit.created_at);
  return (
    <button className={styles.thumb} onClick={onOpen} type="button">
      <div className={styles.thumbTitle}>{extractTitle(unit)}</div>
      {extractDescription(unit.content ?? '') && (
        <div
          className={`md ${styles.thumbDescription}`}
          dangerouslySetInnerHTML={{ __html: marked.parse(extractDescription(unit.content ?? '')) as string }}
        />
      )}
      <div className={styles.thumbMeta}>
        {agent && <MetaBadge label="Agent" value={formatAgentId(agent).toUpperCase()} />}
        {date && <MetaBadge label="Date" value={date} />}
      </div>
    </button>
  );
}

interface DetailModalProps { unit: KnowledgeItem; onClose: () => void }

function DetailModal({ unit, onClose }: DetailModalProps) {
  const agent = unit.metadata?.agent_id as string | undefined;
  const date = formatDate(unit.created_at);
  return (
    <div className={styles.modalBackdrop} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className={styles.modalHeader}>
          <div className={styles.modalTitle}>{extractTitle(unit)}</div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className={`md ${styles.modalBody}`} dangerouslySetInnerHTML={{ __html: marked.parse(stripFirstHeading(unit.content ?? '')) as string }} />
        <div className={styles.modalFooter}>
          {agent && <MetaBadge label="Agent" value={formatAgentId(agent).toUpperCase()} />}
          {date && <MetaBadge label="Date" value={date} />}
        </div>
      </div>
    </div>
  );
}

function TypeSection({
  type, items, emptyMessage, onOpen,
}: {
  type: KnowledgeType;
  items: KnowledgeItem[];
  emptyMessage: string;
  onOpen: (u: KnowledgeItem) => void;
}) {
  return (
    <section className={styles.typeSection}>
      <h2 className={styles.typeTitle}>{type.label} <span className={styles.typeCount}>({items.length})</span></h2>
      {items.length === 0 ? (
        <div className={styles.empty} dangerouslySetInnerHTML={{ __html: marked.parseInline(emptyMessage) as string }} />
      ) : (
        <div className={styles.thumbGrid}>
          {items.map(u => <Thumbnail key={`${u.type}/${u.name}`} unit={u} onOpen={() => onOpen(u)} />)}
        </div>
      )}
    </section>
  );
}

export function KnowledgeView({ config }: { config: AppConfig }) {
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [agent, setAgent] = useState('');
  const [open, setOpen] = useState<KnowledgeItem | null>(null);
  const [searchHits, setSearchHits] = useState<KnowledgeItem[] | null>(null);
  const types: KnowledgeType[] = config.types ?? [];

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<KnowledgeItem[]>('/api/v1/knowledge');
      setItems(Array.isArray(data) ? data : []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  // Live updates via WebSocket: any change to a `kn:*` key triggers a refresh.
  const wsRef = useRef<WebSocket | null>(null);
  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const base = API_BASE || `${proto}//${window.location.host}`;
    const url = `${base.replace(/^http/, 'ws')}/api/v1/knowledge/events?user_id=${encodeURIComponent(getUserId())}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onmessage = () => { void refresh(); };
    ws.onerror = () => {/* network blip — polling will catch up on next mount */};
    return () => { ws.close(); };
  }, []);

  // Debounced semantic search.
  useEffect(() => {
    const q = filter.trim();
    if (!q) { setSearchHits(null); return; }
    const handle = setTimeout(() => {
      apiFetch<KnowledgeItem[]>(`/api/v1/knowledge/search?query=${encodeURIComponent(q)}`)
        .then(d => setSearchHits(Array.isArray(d) ? d : []))
        .catch(() => setSearchHits([]));
    }, 250);
    return () => clearTimeout(handle);
  }, [filter]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  const visible = useMemo(() => {
    const base = searchHits ?? items;
    return agent
      ? base.filter(u => (u.metadata?.agent_id as string | undefined) === agent)
      : base;
  }, [searchHits, items, agent]);

  const byType = useMemo(() => {
    const m = new Map<string, KnowledgeItem[]>();
    for (const t of types) m.set(t.id, []);
    for (const u of visible) {
      if (!m.has(u.type)) m.set(u.type, []);
      m.get(u.type)!.push(u);
    }
    return m;
  }, [visible, types]);

  return (
    <div className={styles.view}>
      <FilterBar
        searchValue={filter}
        onSearch={setFilter}
        agentGroups={config.agent_groups ?? []}
        selectedAgent={agent}
        onAgent={setAgent}
        agentIcons={config.agent_icons}
      />

      {error && <div className={styles.error}>{error}</div>}
      {loading && items.length === 0 && <div className={styles.empty}>Loading…</div>}

      {!loading && types.length === 0 && items.length === 0 && (
        <div className={styles.empty} dangerouslySetInnerHTML={{ __html: marked.parseInline(config.knowledge_empty) as string }} />
      )}

      {!loading && types.length === 0 && items.length > 0 && (
        <div className={styles.thumbGrid}>
          {visible.map(u => <Thumbnail key={`${u.type}/${u.name}`} unit={u} onOpen={() => setOpen(u)} />)}
        </div>
      )}

      {!loading && types.length > 0 && types.map(t => (
        <TypeSection
          key={t.id}
          type={t}
          items={byType.get(t.id) ?? []}
          emptyMessage={config.knowledge_empty}
          onOpen={setOpen}
        />
      ))}

      {open && <DetailModal unit={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
