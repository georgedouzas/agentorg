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

// SSE reader — calls handler for each parsed event object
export async function readSSE(res: Response, handler: (ev: Record<string, unknown>) => void): Promise<void> {
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop()!;
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try { handler(JSON.parse(line.slice(6)) as Record<string, unknown>); } catch { /* skip */ }
    }
  }
}

export type RunEvent = Record<string, unknown> & { type?: string };

// Read a run's SSE stream: each block carries an `event:` name and a JSON `data:` line.
export async function readRunStream(res: Response, onEvent: (name: string, data: RunEvent) => void): Promise<void> {
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
    const blocks = buf.split('\n\n');
    buf = blocks.pop() ?? '';
    for (const block of blocks) {
      const lines = block.split('\n');
      const name = lines.find(l => l.startsWith('event: '))?.slice(7) ?? 'message';
      const dataLine = lines.find(l => l.startsWith('data: '));
      if (!dataLine) continue;
      try { onEvent(name, JSON.parse(dataLine.slice(6)) as RunEvent); } catch { /* skip malformed block */ }
    }
  }
}

// Stream a chat message to an agent or unit as a run.
export function postRun(target: string, userId: string, body: Record<string, unknown>, signal: AbortSignal): Promise<Response> {
  return fetch(`${API_BASE}/api/v1/reasoners/${encodeURIComponent(target)}/stream?user_id=${encodeURIComponent(userId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
}

// Decide an approval as `actor`.
export function decideApproval(id: string, actor: string, approved: boolean, comment = '', edited?: Record<string, unknown>): Promise<unknown> {
  return apiPost(`/api/v1/approvals/${encodeURIComponent(id)}`, { approved, actor, comment, edited_arguments: edited ?? null });
}
