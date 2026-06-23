import type { AppConfig, AgentItem, SelectedAgent } from '../../types';
import styles from './MasterView.module.css';

interface MasterViewProps {
  config: AppConfig;
  agents: AgentItem[];
  onSelect: (agent: SelectedAgent) => void;
}

// The deployed org has ONE platform-level agent: the master. It takes chat from the
// operator and mutates the in-memory spec; the operator redeploys via their CI pipeline.
export function MasterView({ config, agents, onSelect }: MasterViewProps) {
  const master = agents.find(a => a.is_platform);
  if (!master) return <div className={styles.empty}>Master agent not registered.</div>;

  const id = master.agent_id ?? master.id ?? 'master';
  const name = master.name ?? 'Master';
  const icon = config.agent_icons[id] ?? '🛠';

  return (
    <div className={styles.view}>
      <button
        className={styles.card}
        onClick={() => onSelect({ id, name, type: 'agent' })}
        type="button"
      >
        <span className={styles.cardIcon} aria-hidden>{icon}</span>
        <div className={styles.cardBody}>
          <div className={styles.cardName}>{name}</div>
          {master.role && <div className={styles.cardRole}>{master.role}</div>}
        </div>
      </button>
    </div>
  );
}
