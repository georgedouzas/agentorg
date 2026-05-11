import { useEffect, useState } from 'react';
import { apiFetch } from '../api';

export interface SetupStep {
  id: string;
  title: string;
  platform?: string;
  command?: string;
  manual_fallback?: string;
  vars?: string[];
  completed: boolean | null;
  missing_vars?: string[];
}

export interface SetupStatus {
  steps: SetupStep[];
  blocked_count: number;
  pending_count: number;
  total: number;
  all_done: boolean;
}

export function useSetupStatus(refreshKey: number = 0): SetupStatus | null {
  const [data, setData] = useState<SetupStatus | null>(null);

  useEffect(() => {
    apiFetch<SetupStatus>('/api/setup-guide').then(setData).catch(() => null);
  }, [refreshKey]);

  return data;
}
