export interface AppConfig {
  app_name: string;
  app_icon: string;
  app_description: string;
  empty_state: EmptyState;
  knowledge_empty: string;
  types: KnowledgeType[];
  principles: Principles;
  agent_groups: AgentGroup[];
  workflow_groups?: AgentGroup[];
  featured_agents: FeaturedAgent[];
  agent_icons: Record<string, string>;
  overview: OverviewBlock[];
  agent_configs: Record<string, AgentConfig>;
  platform_agent_groups?: AgentGroup[];
}

export interface EmptyState { icon: string; title: string; body: string; }
export interface KnowledgeType { id: string; label: string; metadata_fields?: { name: string; type: string }[]; }
export interface PrincipleParameter {
  name: string;
  type: string;
  default: number | string | boolean;
  label?: string;
  format?: string | null;
}
export interface PrincipleSection { id: string; title: string; body: string; }
export interface Principles { parameters: PrincipleParameter[]; sections: PrincipleSection[]; }

export interface AgentGroup { label: string; ids: string[]; }
export interface FeaturedAgent { id: string; label?: string; accent?: string; }

export interface AgentConfig {
  model: string;
  role: string;
  tools: string[];
  features: string[];
}

export interface OverviewBlock { title: string; body: string; }

export type MessageRole = 'user' | 'assistant' | 'tool' | 'tool-done' | 'step' | 'step-done';
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  isMarkdown?: boolean;
  isStreaming?: boolean;
  toolsCalled?: string[];
}

export interface HitlState {
  workflowId: string;
  runId: string;
  sessionId: string;
  message: string;
  requiresInput: boolean;
}

export interface AgentItem { agent_id?: string; id?: string; name?: string; role?: string; is_platform?: boolean; }
export interface WorkflowItem { workflow_id?: string; id?: string; name?: string; }
export interface SelectedAgent { id: string; name: string; type: 'agent' | 'workflow'; }

export interface KnowledgeItem { name: string; title: string; type: string; agent_id?: string; created_at: string; }
export interface KnowledgeGroup { agent_id: string; agent_name: string; items: KnowledgeItem[]; }
