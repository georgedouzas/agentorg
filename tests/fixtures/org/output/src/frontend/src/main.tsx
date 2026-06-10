import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { API_BASE } from './api'

const NAME_KEY = 'agno_user_name';
const RECENT_KEY = 'agno_recent_users';

function slugify(name: string): string {
  return name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'user';
}

// Staleness check — runs ONCE, before React mounts. If we have a stored user
// but the backend has no record of them (e.g. after `docker compose restart` with
// RESET_ON_STARTUP=1 wiping `org_state`), drop the local identity so the app
// boots straight to the LoginScreen.
async function fetchStateWithRetry(userId: string, retries = 8, delayMs = 600): Promise<{ configured?: boolean } | null> {
  const url = `${API_BASE}/api/v1/parameters?user_id=${encodeURIComponent(userId)}`;
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(url, { cache: 'no-store' });
      if (res.ok) return await res.json();
    } catch { /* keep retrying */ }
    await new Promise(r => setTimeout(r, delayMs));
  }
  return null;
}

async function bootstrap() {
  const storedName = localStorage.getItem(NAME_KEY);
  if (storedName) {
    const userId = slugify(storedName);
    const d = await fetchStateWithRetry(userId);
    // Wipe local identity if (a) backend confirms not configured, or (b) API
    // never came back at all — both mean the user shouldn't be auto-logged-in.
    if (!d || !d.configured) {
      localStorage.removeItem(NAME_KEY);
      localStorage.removeItem(RECENT_KEY);
    }
  }

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

bootstrap();
