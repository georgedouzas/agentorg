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

interface Learning {
  id: number;
  content: string;
  meta_data: Record<string, unknown>;
  created_at: string;
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

/** Description block of a document — everything between the H1 and the first H2.
 * Returned as raw markdown for the caller to render. */
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

function DocumentIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

function BulbIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M9 18h6" />
      <path d="M10 22h4" />
      <path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.4 1 2.3v1h6v-1c0-.9.4-1.8 1-2.3A7 7 0 0 0 12 2z" />
    </svg>
  );
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
  const [subTab, setSubTab] = useState<'documents' | 'learnings'>('documents');

  const [docs, setDocs] = useState<KnowledgeItem[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [docsError, setDocsError] = useState<string | null>(null);
  const [docsFilter, setDocsFilter] = useState('');
  const [docsAgent, setDocsAgent] = useState('');
  const [openDoc, setOpenDoc] = useState<KnowledgeItem | null>(null);

  const [learnings, setLearnings] = useState<Learning[]>([]);
  const [learningsLoading, setLearningsLoading] = useState(false);
  const [learningsFilter, setLearningsFilter] = useState('');
  const [learningsAgent, setLearningsAgent] = useState('');
  const [openLearning, setOpenLearning] = useState<Learning | null>(null);

  useEffect(() => {
    setDocsLoading(true);
    setDocsError(null);
    apiFetch<KnowledgeItem[]>('/api/knowledge')
      .then(data => setDocs(Array.isArray(data) ? data : []))
      .catch(e => setDocsError((e as Error).message))
      .finally(() => setDocsLoading(false));
  }, []);

  useEffect(() => {
    if (subTab === 'learnings' && learnings.length === 0) {
      setLearningsLoading(true);
      apiFetch<Learning[]>('/api/learnings')
        .then(data => setLearnings(Array.isArray(data) ? data : []))
        .catch(() => setLearnings([]))
        .finally(() => setLearningsLoading(false));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subTab]);

  // Lock body scroll when a modal is open
  useEffect(() => {
    const open = openDoc || openLearning;
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [openDoc, openLearning]);


  const dq = docsFilter.trim().toLowerCase();
  const visibleDocs = docs.filter(r => {
    const agent = (r.metadata?.agent_id as string | undefined) ?? '';
    if (docsAgent && agent !== docsAgent) return false;
    if (dq && !(r.name.toLowerCase().includes(dq) || r.content.toLowerCase().includes(dq))) return false;
    return true;
  });

  const lq = learningsFilter.trim().toLowerCase();
  const visibleLearnings = learnings.filter(l => {
    const agent = (l.meta_data?.agent_id as string | undefined) ?? '';
    if (learningsAgent && agent !== learningsAgent) return false;
    if (lq && !l.content.toLowerCase().includes(lq)) return false;
    return true;
  });

  return (
    <div className={styles.view}>
      <div className={styles.subTabs}>
        <div className={styles.searchWrap}>
          <span className={styles.inputIcon}>
            {subTab === 'documents' ? <DocumentIcon /> : <BulbIcon />}
          </span>
          <select
            className={styles.agentSelect}
            value={subTab}
            onChange={e => setSubTab(e.target.value as 'documents' | 'learnings')}
          >
            <option value="documents">Documents</option>
            <option value="learnings">Learnings</option>
          </select>
        </div>
      </div>

      {subTab === 'documents' && (
        <>
          <FilterBar
            searchValue={docsFilter}
            onSearch={setDocsFilter}
            agentGroups={config.agent_groups ?? []}
            selectedAgent={docsAgent}
            onAgent={setDocsAgent}
            searchPlaceholder="Filter by content…"
            agentIcons={config.agent_icons}
          />

          {docsError && <div className={styles.error}>{docsError}</div>}
          {docsLoading && <div className={styles.empty}>Loading…</div>}

          {!docsLoading && !docsError && docs.length === 0 && (
            <div className={styles.empty} dangerouslySetInnerHTML={{ __html: marked.parseInline(config.knowledge_empty.documents) as string }} />
          )}

          {!docsLoading && docs.length > 0 && visibleDocs.length === 0 && (
            <div className={styles.empty}>No documents match these filters</div>
          )}

          <div className={styles.thumbGrid}>
            {visibleDocs.map(r => (
              <Thumbnail
                key={`${r.type}/${r.name}`}
                title={extractTitle(r.content ?? '', r.name)}
                description={extractDescription(r.content ?? '')}
                agent={(r.metadata?.agent_id as string | undefined)}
                date={formatDate(r.created_at)}
                onOpen={() => setOpenDoc(r)}
              />
            ))}
          </div>
        </>
      )}

      {subTab === 'learnings' && (
        <>
          <FilterBar
            searchValue={learningsFilter}
            onSearch={setLearningsFilter}
            agentGroups={config.agent_groups ?? []}
            selectedAgent={learningsAgent}
            onAgent={setLearningsAgent}
            searchPlaceholder="Filter by content…"
            agentIcons={config.agent_icons}
          />

          {learningsLoading && <div className={styles.empty}>Loading…</div>}

          {!learningsLoading && learnings.length === 0 && (
            <div className={styles.empty} dangerouslySetInnerHTML={{ __html: marked.parseInline(config.knowledge_empty.learnings) as string }} />
          )}

          {!learningsLoading && learnings.length > 0 && visibleLearnings.length === 0 && (
            <div className={styles.empty}>No learnings match these filters</div>
          )}

          <div className={styles.thumbGrid}>
            {visibleLearnings.map(l => (
              <Thumbnail
                key={l.id}
                title={extractTitle(l.content ?? '', (l.meta_data?.title as string | undefined) ?? `Learning #${l.id}`)}
                description={extractDescription(l.content ?? '')}
                agent={(l.meta_data?.agent_id as string | undefined)}
                date={formatDate(l.created_at)}
                onOpen={() => setOpenLearning(l)}
              />
            ))}
          </div>
        </>
      )}

      {openDoc && (
        <DetailModal
          title={extractTitle(openDoc.content ?? '', openDoc.name)}
          agent={openDoc.metadata?.agent_id as string | undefined}
          date={formatDate(openDoc.created_at)}
          content={openDoc.content ?? ''}
          onClose={() => setOpenDoc(null)}
        />
      )}
      {openLearning && (
        <DetailModal
          title={extractTitle(openLearning.content ?? '', (openLearning.meta_data?.title as string | undefined) ?? `Learning #${openLearning.id}`)}
          agent={openLearning.meta_data?.agent_id as string | undefined}
          date={formatDate(openLearning.created_at)}
          content={openLearning.content ?? ''}
          onClose={() => setOpenLearning(null)}
        />
      )}
    </div>
  );
}
