import { useState, useEffect } from 'react';
import { apiFetch } from '../api';
import type { AppConfig } from '../types';

const DEFAULT_CONFIG: AppConfig = {
  app_name: "Engineering Team",
  app_icon: "🛠️",
  app_description: "Multi-agent software engineering team that plans, builds, reviews, and ships code",
  empty_state: {
    icon: "🚀",
    title: "No active project",
    body: "Chat with the **Product Manager** to break down requirements, or with the **Tech Lead** to start a code review.",
  },
  knowledge_empty: {
    documents: "No documents yet. Ask the **Architect** to write architecture decisions, or the **Tech Lead** to capture review notes.",
    learnings: "No learnings yet. Agents accumulate patterns and insights automatically as they run.",
  },
  document_types: [{"id": "research", "label": "Architecture Decisions", "metadata_fields": [{"name": "category", "type": "string"}]}, {"id": "report", "label": "Engineering Reports", "metadata_fields": [{"name": "agent_id", "type": "string"}]}],
  state_parameters: [{"default": "Python, TypeScript", "label": "Languages", "name": "languages", "type": "string"}, {"default": 80, "format": "pct", "label": "Min Test Coverage %", "name": "min_coverage_pct", "type": "int"}, {"default": 1, "label": "Min Reviewers", "name": "min_reviewers", "type": "int"}, {"default": "main", "label": "Default Branch", "name": "default_branch", "type": "string"}],
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
