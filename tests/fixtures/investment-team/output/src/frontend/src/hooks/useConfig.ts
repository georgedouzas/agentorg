import { useState, useEffect } from 'react';
import { apiFetch } from '../api';
import type { AppConfig } from '../types';

const DEFAULT_CONFIG: AppConfig = {
  app_name: "Investment Team",
  app_icon: "📈",
  app_description: "Multi-agent equity portfolio management",
  empty_state: {
    icon: "💼",
    title: "Portfolio not yet configured",
    body: "Chat with the **Portfolio Agent** to set up your fund mandate, or use the **Committee Chair** to begin investment analysis.",
  },
  knowledge_empty: {
    documents: "No documents yet. Ask the **Research Analyst** to write company or sector profiles, or the **Memo Writer** to produce investment memos.",
    learnings: "No learnings yet. Agents accumulate patterns and insights automatically as they run.",
  },
  document_types: [{"id": "research", "label": "Research Documents", "metadata_fields": [{"name": "doc_type", "type": "string"}]}, {"id": "memo", "label": "Investment Memos", "metadata_fields": [{"name": "ticker", "type": "string"}]}, {"id": "report", "label": "Agent Reports", "metadata_fields": [{"name": "ticker", "type": "string"}, {"name": "agent_id", "type": "string"}]}],
  state_parameters: [{"default": 10000000, "format": "currency", "group": "Mandate", "label": "Fund Size", "name": "initial_value", "type": "float"}, {"default": "12-18 months", "group": "Mandate", "label": "Investment Horizon", "name": "investment_horizon", "type": "string"}, {"default": "S\u0026P 500", "group": "Mandate", "label": "Benchmark", "name": "benchmark", "type": "string"}, {"default": 10, "group": "Mandate", "label": "Min Market Cap (B)", "name": "min_market_cap_b", "type": "float"}, {"default": 15, "group": "Mandate", "label": "Max Positions", "name": "max_positions", "type": "int"}, {"default": 0.05, "format": "pct", "group": "Mandate", "label": "Cash Reserve %", "name": "cash_reserve_pct", "type": "float"}, {"default": 0.15, "format": "pct", "group": "Mandate", "label": "Max Position %", "name": "max_position_pct", "type": "float"}, {"default": 0.4, "format": "pct", "group": "Mandate", "label": "Max Sector %", "name": "max_sector_pct", "type": "float"}, {"default": 0.25, "format": "pct", "group": "Mandate", "label": "Healthcare Max %", "name": "healthcare_max_pct", "type": "float"}, {"default": 0.2, "format": "pct", "group": "Mandate", "label": "Financials Max %", "name": "financials_max_pct", "type": "float"}, {"default": 0.3, "format": "pct", "group": "Risk Policy", "label": "Max Single Position %", "name": "max_single_position_pct", "type": "float"}, {"default": 0.02, "format": "pct", "group": "Risk Policy", "label": "Min Position %", "name": "min_position_pct", "type": "float"}, {"default": 1.5, "group": "Risk Policy", "label": "High Beta Limit", "name": "high_beta_limit", "type": "float"}, {"default": 0.15, "format": "pct", "group": "Risk Policy", "label": "High Beta Max %", "name": "high_beta_max_pct", "type": "float"}, {"default": 0.15, "format": "pct", "group": "Risk Policy", "label": "High Conviction Min %", "name": "high_conviction_min_pct", "type": "float"}, {"default": 0.25, "format": "pct", "group": "Risk Policy", "label": "High Conviction Max %", "name": "high_conviction_max_pct", "type": "float"}, {"default": 0.05, "format": "pct", "group": "Risk Policy", "label": "Standard Min %", "name": "standard_min_pct", "type": "float"}, {"default": 0.15, "format": "pct", "group": "Risk Policy", "label": "Standard Max %", "name": "standard_max_pct", "type": "float"}, {"default": 0.02, "format": "pct", "group": "Risk Policy", "label": "Exploratory Min %", "name": "exploratory_min_pct", "type": "float"}, {"default": 0.05, "format": "pct", "group": "Risk Policy", "label": "Exploratory Max %", "name": "exploratory_max_pct", "type": "float"}, {"default": 1.5, "group": "Risk Policy", "label": "Max Portfolio Beta", "name": "max_portfolio_beta", "type": "float"}, {"default": 0.2, "format": "pct", "group": "Risk Policy", "label": "Max Drawdown %", "name": "max_drawdown_pct", "type": "float"}, {"default": 0.85, "group": "Risk Policy", "label": "Correlation Limit", "name": "correlation_limit", "type": "float"}, {"default": 0.35, "format": "pct", "group": "Risk Policy", "label": "Appreciation Trim %", "name": "appreciation_trim_pct", "type": "float"}, {"default": 0.25, "format": "pct", "group": "Risk Policy", "label": "Loss Exit %", "name": "loss_exit_pct", "type": "float"}],
  agent_groups: [],
  featured_agents: [],
  agent_icons: {},
  overview: [],
  visualizations: [],
  agent_configs: {},
};

export function useConfig() {
  const [config, setConfig] = useState<AppConfig>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<AppConfig>('/api/config')
      .then(data => setConfig({ ...DEFAULT_CONFIG, ...data }))
      .catch(() => {/* use defaults */})
      .finally(() => setLoading(false));
  }, []);

  return { config, loading };
}
