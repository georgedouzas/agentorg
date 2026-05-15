import type { AppConfig, AgentItem, SelectedAgent } from '../../types';
import styles from './PlatformView.module.css';

interface PlatformViewProps {
  config: AppConfig;
  agents: AgentItem[];
  onSelect: (agent: SelectedAgent) => void;
}

function getId(a: AgentItem): string { return a.agent_id ?? a.id ?? ''; }
function getName(a: AgentItem): string { return a.name ?? getId(a); }

export function PlatformView({ config, agents, onSelect }: PlatformViewProps) {
  const groups = config.platform_agent_groups ?? [];
  const platformAgents = agents.filter(a => a.is_platform);
  const agentMap = new Map(platformAgents.map(a => [getId(a), a]));
  const groupedIds = new Set(groups.flatMap(g => g.ids));
  const ungrouped = platformAgents.filter(a => !groupedIds.has(getId(a)));

  if (platformAgents.length === 0) {
    return <div className={styles.empty}>No platform agents available.</div>;
  }

  function renderCard(a: AgentItem) {
    const id = getId(a);
    const name = getName(a);
    const icon = config.agent_icons[id] ?? '🤖';
    return (
      <button
        key={id}
        className={styles.card}
        onClick={() => onSelect({ id, name, type: 'agent' })}
        type="button"
      >
        <span className={styles.cardIcon} aria-hidden>{icon}</span>
        <div className={styles.cardBody}>
          <div className={styles.cardName}>{name}</div>
          {a.role && <div className={styles.cardRole}>{a.role}</div>}
        </div>
      </button>
    );
  }

  return (
    <div className={styles.view}>
      {groups.map(group => {
        const groupAgents = group.ids.map(id => agentMap.get(id)).filter((a): a is AgentItem => !!a);
        if (groupAgents.length === 0) return null;
        return (
          <section key={group.label} className={styles.section}>
            <h2 className={styles.sectionTitle}>{group.label}</h2>
            <div className={styles.grid}>
              {groupAgents.map(renderCard)}
            </div>
          </section>
        );
      })}
      {ungrouped.length > 0 && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Other</h2>
          <div className={styles.grid}>
            {ungrouped.map(renderCard)}
          </div>
        </section>
      )}
    </div>
  );
}
