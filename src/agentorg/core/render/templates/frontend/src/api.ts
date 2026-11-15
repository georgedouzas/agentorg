// API_BASE is the Railway URL in production, empty string locally.
// It's injected into window by the served HTML (FastAPI replaces __API_BASE_URL__ at serve time).
declare global { interface Window { API_BASE?: string; } }
export const API_BASE: string = (window.API_BASE && window.API_BASE !== '__API_BASE_URL__') ? window.API_BASE : '';

let _userId = 'default';
export const setUserId = (id: string) => { _userId = id; };
export const getUserId = () => _userId;

export function api(path: string): string {
  const sep = path.includes('?') ? '&' : '?';
  return `${API_BASE}${path}${sep}user_id=${encodeURIComponent(_userId)}`;
}

const OPTS: RequestInit = { cache: 'no-store' };

export async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(api(path), OPTS);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(api(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

// Raw fetch (no user_id, for /agents and /workflows which don't need it)
export async function rawFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, OPTS);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

// Decide an approval as `actor`.
export function decideApproval(id: string, actor: string, approved: boolean, comment = '', edited?: Record<string, unknown>): Promise<unknown> {
  return apiPost(`/api/v1/approvals/${encodeURIComponent(id)}`, { approved, actor, comment, edited_arguments: edited ?? null });
}
