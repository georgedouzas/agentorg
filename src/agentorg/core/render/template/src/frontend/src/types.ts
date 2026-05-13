export interface AppConfig {
  app_name: string;
  app_icon: string;
  app_description: string;
  empty_state: EmptyState;
  knowledge_empty: KnowledgeEmpty;
  document_types: DocumentType[];
  state_parameters: StateParameter[];
  agent_groups: AgentGroup[];
  workflow_groups?: AgentGroup[];
  featured_agents: FeaturedAgent[];
  agent_icons: Record<string, string>;
  overview: WidgetConfig[];
  visualizations: ChartConfig[];
  agent_configs: Record<string, AgentConfig>;
}

export interface EmptyState { icon: string; title: string; body: string; }
export interface KnowledgeEmpty { documents: string; learnings: string; }
export interface DocumentType { id: string; label: string; metadata_fields?: { name: string; type: string }[]; }
export interface StateParameter {
  name: string;
  type: string;
  default: number | string | boolean;
  label?: string;
  unit?: string;
  format?: string;
  group?: string;
}

export interface AgentGroup { label: string; ids: string[]; }
export interface FeaturedAgent { id: string; label?: string; accent?: string; }

export interface AgentConfig {
  model: string;
  role: string;
  tools: string[];
  features: string[];
}

export type WidgetType = 'stats-grid' | 'entity-grid' | 'bar-table' | 'feed' | 'candlestick' | 'line' | 'area';

export interface WidgetConfig {
  type: WidgetType;
  title: string;
  endpoint: string;
  id?: string;
  cols?: number;
  action?: { label: string; endpoint: string };
  empty?: string;
}

export interface ChartConfig {
  title: string;
  type: 'candlestick' | 'line' | 'area';
  endpoint: string;
  linked_to?: string;
}

// Widget data shapes — these are the API contracts each widget type expects
export interface StatItem {
  label: string;
  value: string;
  sub?: string;
  trend?: 'pos' | 'neg' | 'neutral';
}

export interface EntityMetric { label: string; value: string; trend?: 'pos' | 'neg'; }
export interface EntityAction { label: string; endpoint: string; }
export interface EntityItem {
  id: string;
  title: string;
  subtitle?: string;
  badge?: string;
  metrics: EntityMetric[];
  actions?: EntityAction[];
}

export interface BarTableRow {
  cells: string[];
  bar?: { value: number; max: number; warn?: boolean };
}
export interface BarTableData {
  headers: string[];
  rows: BarTableRow[];
  action?: { label: string; endpoint: string };
}

export interface FeedItem { title: string; sub?: string; date: string; tag?: string; }

// Chat
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

// Sidebar agent/workflow
export interface AgentItem { agent_id?: string; id?: string; name?: string; }
export interface WorkflowItem { workflow_id?: string; id?: string; name?: string; }
export interface SelectedAgent { id: string; name: string; type: 'agent' | 'workflow'; }

// Reports
export interface AgentReport { id: number; title: string; ticker?: string; created_at: string; }
export interface AgentReportGroup { agent_id: string; agent_name: string; reports: AgentReport[]; }

// OHLCV for candlestick
export interface OHLCVBar { time: string; open: number; high: number; low: number; close: number; }
export interface LinePoint { time: string; value: number; }
