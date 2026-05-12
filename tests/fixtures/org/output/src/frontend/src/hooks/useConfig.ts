import { useState, useEffect } from 'react';
import { apiFetch } from '../api';
import type { AppConfig } from '../types';

const DEFAULT_CONFIG: AppConfig = {
  app_name: "Test Org",
  app_icon: "🔬",
  app_description: "Small research team for testing the agentorg renderer end-to-end.",
  empty_state: {
    icon: "🔬",
    title: "Pick an agent or workflow",
    body: "Try the research pipeline or chat directly with the analyst.",
  },
  knowledge_empty: {
    documents: "No knowledge yet — run the researcher first.",
    learnings: "No learnings accumulated yet.",
  },
  document_types: [{"id": "research", "label": "Research Docs", "metadata_fields": [{"name": "source_count", "type": "int"}]}, {"id": "report", "label": "Analyst Reports", "metadata_fields": [{"name": "agent_id", "type": "string"}]}],
  state_parameters: [{"default": "applied research", "label": "Domain Focus", "name": "domain_focus", "type": "string"}, {"default": 3, "label": "Min Sources per Research Doc", "name": "min_sources", "type": "int"}],
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
