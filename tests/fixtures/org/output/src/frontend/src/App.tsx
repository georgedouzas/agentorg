import { useState, useEffect } from 'react';
import { marked } from 'marked';
import { useIdentity } from './hooks/useIdentity';
import { useConfig } from './hooks/useConfig';
import { useSetupStatus } from './hooks/useSetupStatus';
import { apiFetch } from './api';
import { LoginScreen } from './components/Login/LoginScreen';
import { Header } from './components/Shell/Header';
import { Sidebar } from './components/Shell/Sidebar';
import { AgentPanel } from './components/AgentPanel/AgentPanel';
import { Panel } from './components/Panel/Panel';
import { OverviewView } from './components/Views/OverviewView';
import { KnowledgeView } from './components/Views/KnowledgeView';
import { SettingsView } from './components/Views/SettingsView';
import { PlatformView } from './components/Views/PlatformView';
import { ParameterSetupModal } from './components/Views/ParameterSetupModal';
import type { AgentItem, WorkflowItem, SelectedAgent } from './types';
import styles from './App.module.css';

type Tab = 'overview' | 'knowledge' | 'settings' | 'platform';

interface PanelState {
  open: boolean;
  title: string;
  sub?: string;
  content: string;
}

function OverviewIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
    </svg>
  );
}

function KnowledgeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

function PlatformIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18" />
      <path d="M9 21V9" />
    </svg>
  );
}

export default function App() {
  const identity = useIdentity();
  const { config, loading: configLoading } = useConfig();

  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<SelectedAgent | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [panel, setPanel] = useState<PanelState>({ open: false, title: '', content: '' });
  const [refreshKey] = useState(0);
  const setupStatus = useSetupStatus(refreshKey);
  const [configured, setConfigured] = useState<boolean | null>(null);

  const setupBlocked = !!setupStatus && setupStatus.total > 0 && !setupStatus.all_done;

  useEffect(() => {
    if (!identity.loggedIn) return;
    apiFetch<{ configured: boolean }>('/api/v1/parameters')
      .then(d => setConfigured(d.configured))
      .catch(() => setConfigured(false));
  }, [identity.loggedIn, identity.userId]);

  useEffect(() => {
    if (config.app_name && config.app_name !== 'Agent OS') {
      document.title = config.app_name;
    }
    if (config.app_icon) {
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">${config.app_icon}</text></svg>`;
      const link = (document.querySelector("link[rel='icon']") as HTMLLinkElement) ?? document.createElement('link');
      link.rel = 'icon';
      link.type = 'image/svg+xml';
      link.href = `data:image/svg+xml,${encodeURIComponent(svg)}`;
      if (!link.parentNode) document.head.appendChild(link);
    }
  }, [config.app_name, config.app_icon]);

  useEffect(() => {
    if (!identity.loggedIn) return;
    void apiFetch<AgentItem[]>('/api/v1/agents')
      .then(data => setAgents(Array.isArray(data) ? data : []))
      .catch(() => setAgents([]));

    void apiFetch<WorkflowItem[]>('/api/v1/workflows')
      .then(data => setWorkflows(Array.isArray(data) ? data : []))
      .catch(() => setWorkflows([]));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identity.loggedIn, refreshKey]);

  function handleAgentSelect(agent: SelectedAgent) {
    setSelectedAgent(agent);
  }

  async function handlePanelOpen(title: string, endpoint: string) {
    setPanel({ open: true, title, content: 'Loading…' });
    try {
      const data = await apiFetch<string | Record<string, unknown>>(endpoint);
      let content = '';
      if (typeof data === 'string') {
        content = data;
      } else if (data && typeof data === 'object') {
        const obj = data as Record<string, unknown>;
        content = (obj['content'] as string | undefined)
          ?? (obj['body'] as string | undefined)
          ?? (obj['text'] as string | undefined)
          ?? JSON.stringify(data, null, 2);
      }
      setPanel(prev => ({ ...prev, content }));
    } catch (e) {
      setPanel(prev => ({ ...prev, content: `Error: ${(e as Error).message}` }));
    }
  }

  function closePanel() {
    setPanel(prev => ({ ...prev, open: false }));
  }

  if (!identity.ready) {
    return <div className={styles.splash} />;
  }

  if (!identity.loggedIn) {
    return (
      <LoginScreen
        appName={config.app_name}
        appIcon={config.app_icon}
        appDescription={config.app_description}
        onLogin={identity.login}
      />
    );
  }

  if (configLoading) {
    return <div className={styles.splash} />;
  }

  return (
    <div className={styles.layout}>
      <Header
        appName={config.app_name}
        appIcon={config.app_icon}
        appDescription={config.app_description}
        displayName={identity.displayName}
        onSwitchUser={identity.logout}
      />

      <Sidebar
        config={config}
        agents={agents}
        workflows={workflows}
        selected={selectedAgent}
        onSelect={handleAgentSelect}
        blocked={setupBlocked}
        onBlockedClick={() => setActiveTab('settings')}
      />

      <main className={styles.main}>
        <nav className={styles.tabNav}>
          <button
            className={`${styles.tabBtn} ${activeTab === 'overview' ? styles.tabBtnActive : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            <OverviewIcon /> Overview
          </button>
          <button
            className={`${styles.tabBtn} ${activeTab === 'platform' ? styles.tabBtnActive : ''}`}
            onClick={() => setActiveTab('platform')}
          >
            <PlatformIcon /> Platform
          </button>
          <button
            className={`${styles.tabBtn} ${activeTab === 'knowledge' ? styles.tabBtnActive : ''}`}
            onClick={() => setActiveTab('knowledge')}
          >
            <KnowledgeIcon /> Knowledge
          </button>
          <button
            className={`${styles.tabBtn} ${activeTab === 'settings' ? styles.tabBtnActive : ''}`}
            onClick={() => setActiveTab('settings')}
          >
            <SettingsIcon /> Settings
            {setupBlocked && <span className={styles.tabDot} aria-hidden />}
          </button>
        </nav>

        <div className={styles.viewArea}>
          {activeTab === 'overview' && (
            <OverviewView
              config={config}
              configured={configured === true}
              onPanelOpen={handlePanelOpen}
            />
          )}
          {activeTab === 'knowledge' && (
            <KnowledgeView config={config} />
          )}
          {activeTab === 'settings' && (
            <SettingsView
              orgName={config.app_name}
              setupStatus={setupStatus}
            />
          )}
          {activeTab === 'platform' && (
            <PlatformView
              config={config}
              agents={agents}
              onSelect={setSelectedAgent}
            />
          )}
        </div>
      </main>

      {selectedAgent && (
        <AgentPanel
          selected={selectedAgent}
          config={config}
          userId={identity.userId ?? 'default'}
          onClose={() => setSelectedAgent(null)}
        />
      )}

      <Panel
        open={panel.open}
        title={panel.title}
        sub={panel.sub}
        onClose={closePanel}
      >
        <div
          className="md"
          dangerouslySetInnerHTML={{
            __html: marked.parse(panel.content) as string,
          }}
        />
      </Panel>

      {configured === false && (
        <ParameterSetupModal
          parameters={config.parameters ?? []}
          onConfigured={() => setConfigured(true)}
        />
      )}
    </div>
  );
}
