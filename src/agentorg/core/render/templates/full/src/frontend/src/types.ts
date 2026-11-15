export interface AppConfig {
  app_name: string;
  app_icon: string;
  app_description: string;
  name_is_placeholder?: boolean;
  description_is_placeholder?: boolean;
  empty_state: EmptyState;
  knowledge_empty: string;
  types: KnowledgeType[];
  parameters: Parameter[];
  principles: Principles;
  agent_groups: AgentGroup[];
  workflow_groups?: AgentGroup[];
  featured_agents: FeaturedAgent[];
  agent_icons: Record<string, string>;
  overview: OverviewBlock[];
  agent_configs: Record<string, AgentConfig>;
  platform_agents?: { id: string; name: string }[];
  units?: UnitSummary[];
  principles_owner?: string;
  chat_url?: string;
}

export interface EmptyState { icon: string; title: string; body: string; }
export interface KnowledgeType { id: string; label: string; metadata_fields?: { name: string; type: string }[]; }
export interface Parameter {
  name: string;
  type: string;
  default: number | string | boolean;
  label?: string;
  format?: string | null;
  group?: string;
  unit?: string;
}
export interface PrincipleSection { id: string; title: string; body: string; }
export interface Principles { sections: PrincipleSection[]; }

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
  approvalId: string;
  message: string;
}

export interface AgentItem { agent_id?: string; id?: string; name?: string; role?: string; is_platform?: boolean; }
export interface WorkflowItem { workflow_id?: string; id?: string; name?: string; }
export interface SelectedAgent { id: string; name: string; type: 'agent' | 'workflow'; }

export interface KnowledgeItem { name: string; title: string; type: string; agent_id?: string; created_at: string; }
export interface KnowledgeGroup { agent_id: string; agent_name: string; items: KnowledgeItem[]; }

export interface UnitSummary { id: string; name: string; model: string; lead: string | null; members: string[]; }

export interface RunSummary {
  id: string;
  target: string;
  trigger_kind: string;
  trigger_id: string | null;
  parent_id: string | null;
  status: string;
  failure_reason: string | null;
  output: unknown;
  cost_usd: number;
  created_at: string | null;
  ended_at: string | null;
}

export interface RunDetail extends RunSummary {
  prompt: string;
  transcript: Record<string, unknown>[];
  children: RunSummary[];
}

export interface ApprovalItem {
  id: string;
  run_id: string;
  action_class: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  approvers: string[];
  created_at: string;
}

export interface InboxEntry { id: string; kind: string; run_id: string | null; reason: string; context: Record<string, unknown>; created_at: string; }

export interface LifecycleEvent { from: string | null; to: string; actor: string; reason: string; at: string; }
export interface LifecycleInfo { state: string; reason: string; history: LifecycleEvent[]; }
