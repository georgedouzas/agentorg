import { useState, useEffect } from 'react';
import { apiFetch } from '../api';
import type { AppConfig } from '../types';

const DEFAULT_CONFIG: AppConfig = {
  app_name: "Org",
  app_icon: "🔬",
  app_description: "Small research team for testing the agentorg renderer end-to-end.",
  empty_state: {
    icon: "🔬",
    title: "Pick an agent or workflow",
    body: "Try the research pipeline or chat directly with the analyst.",
  },
  knowledge_empty: "No knowledge yet, run the researcher first.",
  types: [{"id": "research", "label": "Research Docs", "metadata_fields": []}, {"id": "report", "label": "Analyst Reports", "metadata_fields": []}],
  parameters: [{"default": "Applied Research", "format": null, "label": "Domain Focus", "name": "domain_focus", "type": "string"}, {"default": 3, "format": null, "label": "Minimum Sources", "name": "min_sources", "type": "int"}],
  principles: {"sections": [{"body": "- Focus area: {domain_focus}\n- Every research doc cites at least {min_sources} sources.\n- Reports are structured around Overview, Findings, Implications, and Open Questions.", "id": "mission", "title": "Mission"}, {"body": "- Researcher gathers material and writes research docs.\n- Analyst synthesises research into a final report.\n- Neither agent auto-saves; the user is asked before anything is persisted.", "id": "process", "title": "Process"}]},
  agent_groups: [],
  featured_agents: [],
  agent_icons: {},
  overview: [],
  agent_configs: {},
};

export function useConfig() {
  const [config, setConfig] = useState<AppConfig>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<AppConfig>('/api/v1/config')
      .then(data => setConfig({ ...DEFAULT_CONFIG, ...data }))
      .catch(() => {/* use defaults */})
      .finally(() => setLoading(false));
  }, []);

  return { config, loading };
}
