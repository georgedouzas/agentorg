import { marked } from 'marked';
import type { AppConfig } from '../../types';
import { useSetupStatus } from '../../hooks/useSetupStatus';
import styles from './DashboardView.module.css';

interface DashboardViewProps {
  config: AppConfig;
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

// Dashboard elements are always org-specific - they're custom markdown blocks the
// master agent emits during Build (e.g. "Sales Pipeline", "Inventory Summary"). When
// nothing has been emitted yet, we say so plainly. No hero card, no welcome ceremony -
// the org's name + tagline live on the page chrome (header), not here.
export function DashboardView({ config }: DashboardViewProps) {
  const blocks = config.overview ?? [];
  return (
    <div className={styles.view}>
      {blocks.length === 0 ? (
        <section className={styles.empty}>
          <div className={styles.emptyIcon} aria-hidden>▦</div>
          <div className={styles.emptyTitle}>No dashboard elements yet.</div>
          <div className={styles.emptyBody}>
            Org-specific dashboard blocks during build will appear here.
          </div>
        </section>
      ) : (
        blocks.map(block => (
          <section key={block.title} className={styles.section}>
            <h2 className={styles.sectionTitle}>{block.title}</h2>
            <div className="md" dangerouslySetInnerHTML={{ __html: marked.parse(block.body) as string }} />
          </section>
        ))
      )}
      <SetupHealth />
    </div>
  );
}
