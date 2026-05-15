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

function CharterSection({ config }: { config: AppConfig }) {
  const sections = config.charter?.sections ?? [];
  if (sections.length === 0) return null;
  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>Charter</h2>
      {sections.map(s => (
        <div key={s.id} className={styles.group}>
          <h3 className={styles.groupLabel}>{s.title}</h3>
          <div className="md" dangerouslySetInnerHTML={{ __html: marked.parse(s.body) as string }} />
        </div>
      ))}
    </section>
  );
}

function CustomBlocks({ config }: { config: AppConfig }) {
  if (config.overview.length === 0) return null;
  return (
    <>
      {config.overview.map(block => (
        <section key={block.title} className={styles.section}>
          <h2 className={styles.sectionTitle}>{block.title}</h2>
          <div className="md" dangerouslySetInnerHTML={{ __html: marked.parse(block.body) as string }} />
        </section>
      ))}
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

function RecentActivity({ config, onPanelOpen }: { config: AppConfig; onPanelOpen: (title: string, endpoint: string) => void }) {
  const [items, setItems] = useState<KnowledgeItem[] | null>(null);
  useEffect(() => {
    apiFetch<KnowledgeItem[]>('/api/v1/knowledge?limit=5')
      .then(d => setItems(Array.isArray(d) ? d : []))
      .catch(() => setItems([]));
  }, []);

  if (items === null) return null;

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>Recent Activity</h2>
      {items.length === 0 ? (
        <div className={styles.muted}>{config.knowledge_empty}</div>
      ) : (
        <ul className={styles.itemList}>
          {items.map(it => (
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

export function OverviewView({ config, onPanelOpen }: OverviewViewProps) {
  return (
    <div className={styles.view}>
      <CharterSection config={config} />
      <CustomBlocks config={config} />
      <RecentActivity config={config} onPanelOpen={onPanelOpen} />
      <SetupHealth />
    </div>
  );
}
