import { useEffect, useState } from 'react';
import { marked } from 'marked';
import { apiFetch } from '../../api';
import type { AppConfig, KnowledgeItem } from '../../types';
import { useSetupStatus } from '../../hooks/useSetupStatus';
import styles from './OverviewView.module.css';

interface OverviewViewProps {
  config: AppConfig;
  configured: boolean;
  onPanelOpen: (title: string, endpoint: string) => void;
}

function ParameterList({ config, configured }: { config: AppConfig; configured: boolean }) {
  const params = config.parameters ?? [];
  const [values, setValues] = useState<Record<string, unknown>>(() =>
    Object.fromEntries(params.map(p => [p.name, p.default])),
  );
  useEffect(() => {
    if (!configured) return;
    apiFetch<{ parameters: Record<string, unknown> }>('/api/v1/parameters')
      .then(s => setValues((v: Record<string, unknown>) => ({ ...v, ...(s.parameters ?? {}) })))
      .catch(() => {/* fall back to defaults */});
  }, [configured]);
  if (params.length === 0) return null;
  return (
    <dl className={styles.paramList}>
      {params.map(p => (
        <div key={p.name} className={styles.paramRow}>
          <dt className={styles.paramLabel}>{p.label ?? p.name}</dt>
          <dd className={styles.paramValue}>{String(values[p.name] ?? p.default)}</dd>
        </div>
      ))}
    </dl>
  );
}

function PrinciplesSection({ config, configured }: { config: AppConfig; configured: boolean }) {
  const sections = config.principles?.sections ?? [];
  const hasParams = (config.parameters ?? []).length > 0;
  // Always show the section heading even when empty, same as Recent Activity. The
  // dashboard's structure should be stable across stages - blocks appear/fill in but
  // don't pop into existence.
  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>Principles</h2>
      <ParameterList config={config} configured={configured} />
      {sections.length === 0 && !hasParams ? (
        <div className={styles.muted}>No principles defined yet.</div>
      ) : (
        sections.map(s => (
          <div key={s.id} className={styles.group}>
            <h3 className={styles.groupLabel}>{s.title}</h3>
            <div className="md" dangerouslySetInnerHTML={{ __html: marked.parse(s.body) as string }} />
          </div>
        ))
      )}
    </section>
  );
}

function DashboardTab({ config }: { config: AppConfig }) {
  // The Dashboard tab is the high-value work surface. It shows custom overview blocks
  // emitted by the master agent during Build (org-specific dashboards: pipelines,
  // inventory views, KPIs, whatever), plus Setup Health as a quick-glance.
  // Empty state until the org grows past trivial.
  const hasBlocks = (config.overview ?? []).length > 0;
  return (
    <>
      {!hasBlocks && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Dashboard</h2>
          <div className={styles.muted}>Your dashboard fills in as your org grows.</div>
        </section>
      )}
      {hasBlocks && config.overview.map(block => (
        <section key={block.title} className={styles.section}>
          <h2 className={styles.sectionTitle}>{block.title}</h2>
          <div className="md" dangerouslySetInnerHTML={{ __html: marked.parse(block.body) as string }} />
        </section>
      ))}
      <SetupHealth />
    </>
  );
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

function RecentActivity({ onPanelOpen }: { onPanelOpen: (title: string, endpoint: string) => void }) {
  const [items, setItems] = useState<KnowledgeItem[] | null>(null);
  useEffect(() => {
    apiFetch<KnowledgeItem[]>('/api/v1/knowledge?limit=5')
      .then(d => setItems(Array.isArray(d) ? d : []))
      .catch(() => setItems([]));
  }, []);

  // Render the heading even before the first fetch resolves so the section is stable.
  const empty = items === null || items.length === 0;

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>Recent Activity</h2>
      {empty ? (
        <div className={styles.muted}>No recent activity yet.</div>
      ) : (
        <ul className={styles.itemList}>
          {items!.map(it => (
            <li key={`${it.type}/${it.name}`} className={styles.item}>
              <button
                type="button"
                className={styles.itemBtn}
                onClick={() => onPanelOpen(it.title, `/api/v1/knowledge/${encodeURIComponent(it.type)}/${encodeURIComponent(it.name)}`)}
              >
                <span className={styles.itemName}>{it.title}</span>
                <span className={styles.itemMeta}>{formatDate(it.created_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SetupHealth() {
  const status = useSetupStatus();
  if (!status || !status.steps || status.steps.length === 0) return null;
  const completed = status.steps.filter(s => s.completed === true).length;
  const blocked = status.steps.filter(s => s.completed === false);

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>Setup Health</h2>
      <div className={styles.muted}>
        {completed}/{status.steps.length} steps complete.
      </div>
      {blocked.length > 0 && (
        <ul className={styles.itemList}>
          {blocked.map(s => (
            <li key={s.id} className={styles.item}>
              <span className={styles.itemIcon} aria-hidden>⚠</span>
              <span className={styles.itemName}>{s.title}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

type OverviewSectionId = 'dashboard' | 'principles' | 'activity';

const RAIL_ITEMS: { id: OverviewSectionId; label: string; icon: string }[] = [
  // Lucide-style 16x16 inline SVGs - no external icon font, no per-icon import cost.
  { id: 'dashboard',  label: 'Dashboard',  icon: 'M3 13h8V3H3v10zm10 8h8V11h-8v10zM3 21h8v-6H3v6zm10-18v6h8V3h-8z' },
  { id: 'principles', label: 'Principles', icon: 'M19 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2zM7 7h10v2H7V7zm0 4h10v2H7v-2zm0 4h7v2H7v-2z' },
  { id: 'activity',   label: 'Activity',   icon: 'M22 12h-4l-3 9L9 3l-3 9H2' },
];

function RailIcon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={d} />
    </svg>
  );
}

export function OverviewView({ config, configured, onPanelOpen }: OverviewViewProps) {
  const [active, setActive] = useState<OverviewSectionId>('dashboard');
  return (
    <div className={styles.view}>
      <nav className={styles.rail} aria-label="Overview sections">
        {RAIL_ITEMS.map(it => (
          <button
            key={it.id}
            type="button"
            aria-current={active === it.id ? 'page' : undefined}
            className={`${styles.railItem} ${active === it.id ? styles.railItemActive : ''}`}
            onClick={() => setActive(it.id)}
          >
            <span className={styles.railIcon}><RailIcon d={it.icon} /></span>
            <span>{it.label}</span>
          </button>
        ))}
      </nav>
      <div className={styles.tabPanel}>
        {active === 'dashboard' && <DashboardTab config={config} />}
        {active === 'principles' && <PrinciplesSection config={config} configured={configured} />}
        {active === 'activity' && <RecentActivity onPanelOpen={onPanelOpen} />}
      </div>
    </div>
  );
}
