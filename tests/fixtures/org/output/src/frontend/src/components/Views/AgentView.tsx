import { useState, useEffect } from 'react';
import { apiFetch } from '../../api';
import type { AppConfig, SelectedAgent, AgentReport, AgentConfig } from '../../types';
import styles from './AgentView.module.css';

interface AgentViewProps {
  selected: SelectedAgent;
  config: AppConfig;
  onPanelOpen: (title: string, endpoint: string) => void;
}

const FEATURE_LABELS: Record<string, string> = {
  knowledge_search:       'Knowledge Search',
  institutional_learning: 'Institutional Learning',
  agentic_memory:         'Agentic Memory',
  session_history:        'Session History',
};

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

function AgentConfigCard({ agentConfig }: { agentConfig: AgentConfig }) {
  return (
    <div className={styles.configCard}>
      <div className={styles.configRow}>
        <span className={styles.configLabel}>Model</span>
        <span className={styles.configValue}>{agentConfig.model}</span>
      </div>
      <div className={styles.configRow}>
        <span className={styles.configLabel}>Role</span>
        <span className={styles.configValue}>{agentConfig.role}</span>
      </div>
      <div className={styles.configRow}>
        <span className={styles.configLabel}>Tools</span>
        <div className={styles.tagList}>
          {agentConfig.tools.map(t => (
            <span key={t} className={styles.toolTag}>{t}</span>
          ))}
        </div>
      </div>
      <div className={styles.configRow}>
        <span className={styles.configLabel}>Features</span>
        <div className={styles.tagList}>
          {agentConfig.features.map(f => (
            <span key={f} className={`${styles.featureTag}`}>{FEATURE_LABELS[f] ?? f}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

export function AgentView({ selected, config, onPanelOpen }: AgentViewProps) {
  const [reports, setReports] = useState<AgentReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isFeatured = config.featured_agents.some(f => f.id === selected.id);
  const icon = config.agent_icons[selected.id] ?? (selected.type === 'workflow' ? '⚡' : '🤖');

  const group = config.agent_groups.find(g => g.ids.includes(selected.id));
  const typeLabel = selected.type === 'workflow' ? 'Workflow' : (group?.label ?? 'Agent');

  const agentConfig: AgentConfig | undefined = config.agent_configs[selected.id];

  async function fetchReports() {
    if (selected.type === 'workflow') return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<{ agents: { agent_id: string; reports: AgentReport[] }[] }>(
        `/api/agent-reports?agent_id=${encodeURIComponent(selected.id)}`
      );
      const list = data.agents?.[0]?.reports ?? [];
      setReports(list);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void fetchReports();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected.id]);

  return (
    <div className={styles.view}>
      <div className={styles.agentHeader}>
        <span className={styles.agentIcon}>{icon}</span>
        <div className={styles.agentMeta}>
          <h2 className={`${styles.agentName} ${isFeatured ? styles.agentNameFeatured : ''}`}>
            {selected.name}
          </h2>
          <span className={styles.agentType}>{typeLabel}</span>
        </div>
      </div>

      {agentConfig && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Configuration</h3>
          <AgentConfigCard agentConfig={agentConfig} />
        </section>
      )}

      {selected.type !== 'workflow' && (
        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3 className={styles.sectionTitle}>Analysis Reports</h3>
            <button className={styles.refreshBtn} onClick={() => void fetchReports()} disabled={loading}>
              {loading ? '…' : '↻ Refresh'}
            </button>
          </div>

          {error && <div className={styles.error}>{error}</div>}

          {!loading && reports.length === 0 && !error && (
            <div className={styles.empty}>No reports yet. Chat with this agent to generate analysis.</div>
          )}

          <div className={styles.reportList}>
            {reports.map(report => (
              <button
                key={report.name}
                className={styles.reportRow}
                onClick={() => onPanelOpen(report.title, `/api/agent-reports/${encodeURIComponent(report.name)}`)}
              >
                <div className={styles.reportLeft}>
                  <span className={styles.reportTitle}>{report.title}</span>
                  {report.ticker && (
                    <span className={styles.reportTicker}>{report.ticker}</span>
                  )}
                </div>
                <span className={styles.reportDate}>{formatDate(report.created_at)}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {selected.type === 'workflow' && (
        <section className={styles.section}>
          <div className={styles.empty}>
            Use the chat below to run this workflow. Results and generated memos will appear in the relevant agent views.
          </div>
        </section>
      )}
    </div>
  );
}
