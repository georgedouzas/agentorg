import { useState, useEffect } from 'react';
import { setUserId } from '../api';

const NAME_KEY = 'agno_user_name';
const RECENT_KEY = 'agno_recent_users';

// True when the rendered org is embedded in `agentorg ui`'s preview iframe. Master UI
// sets VITE_AGENTORG_PREVIEW_MODE on the Vite subprocess; the value is baked into the
// bundle. In preview we auto-log-in as 'Preview' so the iframe lands on the dashboard
// without going through the name-prompt screen on every reload.
const PREVIEW_MODE = import.meta.env.VITE_AGENTORG_PREVIEW_MODE === 'true';

function slugify(name: string): string {
  return name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'user';
}

export function getRecentUsers(): string[] {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]') as string[]; } catch { return []; }
}

function saveRecent(name: string) {
  const recent = getRecentUsers().filter(n => n !== name);
  recent.unshift(name);
  localStorage.setItem(RECENT_KEY, JSON.stringify(recent.slice(0, 6)));
}

export function useIdentity() {
  const [userId, setUserIdState] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (PREVIEW_MODE) {
      // Auto-login in preview - skip the name-prompt screen entirely.
      const id = 'preview';
      setDisplayName('Preview');
      setUserIdState(id);
      setUserId(id);
      setReady(true);
      return;
    }
    const stored = localStorage.getItem(NAME_KEY);
    if (stored) {
      const id = slugify(stored);
      setDisplayName(stored);
      setUserIdState(id);
      setUserId(id);
    }
    setReady(true);
  }, []);

  function login(name: string) {
    const id = slugify(name);
    localStorage.setItem(NAME_KEY, name);
    saveRecent(name);
    setDisplayName(name);
    setUserIdState(id);
    setUserId(id);
  }

  function logout() {
    localStorage.removeItem(NAME_KEY);
    setDisplayName(null);
    setUserIdState(null);
    setUserId('default');
  }

  return { userId, displayName, ready, loggedIn: !!userId, login, logout };
}
