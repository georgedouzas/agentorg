import styles from './Sidebar.module.css';
import type { AppConfig, AgentItem, WorkflowItem, SelectedAgent } from '../../types';

interface SidebarProps {
  config: AppConfig;
  agents: AgentItem[];
  workflows: WorkflowItem[];
  selected: SelectedAgent | null;
  onSelect: (agent: SelectedAgent) => void;
  blocked?: boolean;
  onBlockedClick?: () => void;
}

function getAgentId(a: AgentItem): string { return a.agent_id ?? a.id ?? ''; }
function getAgentName(a: AgentItem): string { return a.name ?? getAgentId(a); }
function getWorkflowId(w: WorkflowItem): string { return w.workflow_id ?? w.id ?? ''; }
function getWorkflowName(w: WorkflowItem): string { return w.name ?? getWorkflowId(w); }
function formatId(id: string): string {
  return id.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export function Sidebar({ config, agents, workflows, selected, onSelect, blocked, onBlockedClick }: SidebarProps) {
  // Platform agents live on the dedicated `Platform` tab — keep them out of the org sidebar entirely.
  const orgAgents = agents.filter(a => !a.is_platform);

  const featuredIds = new Set(config.featured_agents.map(f => f.id));
  const groupedIds = new Set(config.agent_groups.flatMap(g => g.ids));
  const agentMap = new Map(orgAgents.map(a => [getAgentId(a), a]));

  const ungroupedAgents = orgAgents.filter(a => {
    const id = getAgentId(a);
    return !groupedIds.has(id) && !featuredIds.has(id);
  });

  function renderItem(id: string, name: string, type: 'agent' | 'workflow') {
    const isSelected = selected?.id === id && selected?.type === type;
    const isFeatured = type === 'agent' && featuredIds.has(id);
    const icon = config.agent_icons[id] ?? (type === 'workflow' ? '⚡' : '🤖');
    const isDisabled = !!blocked;

    return (
      <button
        key={id}
        className={`${styles.item} ${isSelected ? styles.itemActive : ''} ${isFeatured ? styles.itemFeatured : ''} ${isDisabled ? styles.itemDisabled : ''}`}
        onClick={() => isDisabled ? onBlockedClick?.() : onSelect({ id, name, type })}
        title={isDisabled ? 'Complete setup first' : undefined}
      >
        <span className={styles.itemIcon}>{icon}</span>
        <span className={styles.itemName}>{name}</span>
      </button>
    );
  }

  const hasAgents = config.agent_groups.length > 0 || ungroupedAgents.length > 0;

  return (
    <aside className={styles.sidebar}>
      <div className={styles.scrollArea}>
      {hasAgents && (
        <div className={styles.section}>
          <div className={styles.sectionLabel}>Agents</div>
          {config.agent_groups.map(group => {
            const isPlatformGroup = group.label === 'Platform';
            return (
              <div
                key={group.label}
                className={`${styles.group} ${isPlatformGroup ? styles.platformGroup : ''}`}
              >
                <div className={styles.groupLabel}>{group.label}</div>
                {group.ids.map(id => {
                  const a = agentMap.get(id);
                  const name = a ? getAgentName(a) : formatId(id);
                  return renderItem(id, name, 'agent');
                })}
              </div>
            );
          })}
          {ungroupedAgents.length > 0 && (
            <div className={styles.group}>
              <div className={styles.groupLabel}>Other</div>
              {ungroupedAgents.map(a => renderItem(getAgentId(a), getAgentName(a), 'agent'))}
            </div>
          )}
        </div>
      )}

      {workflows.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionLabel}>Workflows</div>
          {(() => {
            const wfGroups = config.workflow_groups ?? [];
            const wfMap = new Map(workflows.map(w => [getWorkflowId(w), w]));
            const groupedWfIds = new Set(wfGroups.flatMap(g => g.ids));
            const ungroupedWfs = workflows.filter(w => !groupedWfIds.has(getWorkflowId(w)));
            return (
              <>
                {wfGroups.map(group => (
                  <div key={group.label} className={styles.group}>
                    <div className={styles.groupLabel}>{group.label}</div>
                    {group.ids.map(id => {
                      const w = wfMap.get(id);
                      const name = w ? getWorkflowName(w) : formatId(id);
                      return renderItem(id, name, 'workflow');
                    })}
                  </div>
                ))}
                {ungroupedWfs.length > 0 && (
                  <div className={styles.group}>
                    <div className={styles.groupLabel}>Pipelines</div>
                    {ungroupedWfs.map(w => renderItem(getWorkflowId(w), getWorkflowName(w), 'workflow'))}
                  </div>
                )}
              </>
            );
          })()}
        </div>
      )}
      </div>
    </aside>
  );
}
