import { useState, useRef, useEffect, useCallback, KeyboardEvent } from 'react';
import { marked } from 'marked';
import { API_BASE, api, apiFetch } from '../../api';
import type { AppConfig, ChatMessage, HitlState, SelectedAgent } from '../../types';
import styles from './AgentPanel.module.css';

type PanelTab = 'chat' | 'config';

// ── Description pane ─────────────────────────────────────────────────────────

interface AgentInfo {
  id: string;
  name: string;
  role: string;
  model: string;
  tools: string[];
  instructions: string;
}

function DescriptionPane({ agentId }: { agentId: string }) {
  const [info, setInfo] = useState<AgentInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiFetch<AgentInfo>(`/api/v1/agents/${encodeURIComponent(agentId)}`)
      .then(d => setInfo(d))
      .catch(() => setInfo(null))
      .finally(() => setLoading(false));
  }, [agentId]);

  if (loading) return <div className={styles.empty}>Loading…</div>;
  if (!info)   return <div className={styles.empty}>No information available for this agent.</div>;

  const toolsLabel = info.tools.map(t => t.replace(/_/g, ' ').toUpperCase()).join(', ');

  return (
    <div className={styles.descCard}>
      {info.instructions && (
        <div className={styles.descSection} style={{ borderTop: 'none', paddingTop: 0 }}>
          <div className="md" dangerouslySetInnerHTML={{ __html: marked.parse(info.instructions) as string }} />
        </div>
      )}

      <div className={styles.badgeStack}>
        {info.model && <MetaBadge label="Model" value={info.model.toUpperCase()} />}
        {toolsLabel && <MetaBadge label="Tools" value={toolsLabel} />}
      </div>
    </div>
  );
}

function MetaBadge({ label, value }: { label: string; value: string }) {
  return (
    <span className="badge">
      <span className="badge-label">{label}</span>
      <span className="badge-value">{value}</span>
    </span>
  );
}

// ── Chat pane ─────────────────────────────────────────────────────────────────

interface CachedChatState { messages: ChatMessage[]; hitlState: HitlState | null; }

let msgIdCounter = 0;
function nextId(): string { return `m${++msgIdCounter}`; }

function renderContent(msg: ChatMessage): string {
  if (msg.isMarkdown) return marked.parse(msg.content) as string;
  return msg.content.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function titleize(name: string): string {
  return name.replace(/[_-]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function ChatPane({ selected, userId }: { selected: SelectedAgent; userId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [hitlState, setHitlState] = useState<HitlState | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [input, setInput] = useState('');
  const [hitlInput, setHitlInput] = useState('');
  const [currentTool, setCurrentTool] = useState<string | null>(null);

  const cache = useRef<Map<string, CachedChatState>>(new Map());
  const prevSelected = useRef<SelectedAgent | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const prev = prevSelected.current;
    if (prev) cache.current.set(prev.id, { messages, hitlState });
    prevSelected.current = selected;
    const cached = cache.current.get(selected.id);
    if (cached) {
      setMessages(cached.messages);
      setHitlState(cached.hitlState);
      setInput('');
      return;
    }
    setMessages([]);
    setHitlState(null);
    setInput('');
    // Session history is an AgentOS concept; AgentField has no equivalent endpoint yet, so we
    // start every selection with an empty chat. Per-agent in-memory cache above still survives.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  function autoResize() {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  }

  const updateLastAssistant = useCallback((updater: (m: ChatMessage) => ChatMessage) => {
    setMessages(prev => {
      const idx = [...prev].reverse().findIndex(m => m.role === 'assistant');
      if (idx === -1) return prev;
      const real = prev.length - 1 - idx;
      const next = [...prev];
      next[real] = updater(next[real]!);
      return next;
    });
  }, []);

  async function send() {
    if (!input.trim() || streaming) return;
    const text = input.trim();
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';

    setMessages(prev => [...prev, { id: nextId(), role: 'user', content: text }]);
    setStreaming(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      // Stable session id per (user, agent) so agno's memory threads turns of the same chat.
      const sessionKey = `session_${userId}_${selected.id}`;
      let sessionId = localStorage.getItem(sessionKey);
      if (!sessionId) {
        sessionId = `${selected.id}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
        localStorage.setItem(sessionKey, sessionId);
      }

      // Stream agno events via SSE: tokens land in the assistant bubble live, reasoning
      // traces (`<thinking>...</thinking>`) are hidden — including unclosed ones mid-stream.
      const res = await fetch(`${API_BASE}/api/v1/reasoners/${encodeURIComponent(selected.id)}/stream?user_id=${encodeURIComponent(userId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId, user_id: userId }),
        signal: ctrl.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const assistantId = nextId();
      setMessages(prev => [...prev, {
        id: assistantId,
        role: 'assistant',
        content: '',
        isMarkdown: true,
        isStreaming: true,
      }]);

      let raw = '';
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      const stripThinking = (s: string) => {
        let out = s.replace(/<thinking>[\s\S]*?<\/thinking>/gi, '');
        const idx = out.search(/<thinking>/i);
        return (idx >= 0 ? out.slice(0, idx) : out).trimStart();
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        // sse-starlette uses CRLF line endings; normalise to LF before splitting.
        buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
        const blocks = buf.split('\n\n');
        buf = blocks.pop() ?? '';
        for (const block of blocks) {
          const dataLine = block.split('\n').find(l => l.startsWith('data: '));
          if (!dataLine) continue;
          let ev: { event?: string; content?: string; error?: string; tool_name?: string };
          try { ev = JSON.parse(dataLine.slice(6)) as typeof ev; } catch { continue; }
          if (ev.event === 'RunContent' && ev.content) {
            raw += ev.content;
            const display = stripThinking(raw);
            updateLastAssistant(m => ({ ...m, content: display }));
          } else if (ev.event === 'RunCompleted' && ev.content) {
            raw = ev.content;
            updateLastAssistant(m => ({ ...m, content: stripThinking(raw), isStreaming: false }));
          } else if (ev.event === 'ToolCallStarted' && ev.tool_name) {
            setCurrentTool(ev.tool_name);
            updateLastAssistant(m => ({
              ...m,
              toolsCalled: [...(m.toolsCalled ?? []), ev.tool_name as string],
            }));
          } else if (ev.event === 'ToolCallCompleted') {
            setCurrentTool(null);
          } else if (ev.event === 'RunError') {
            updateLastAssistant(m => ({ ...m, content: ev.error || 'An error occurred', isStreaming: false }));
          }
        }
      }
      updateLastAssistant(m => ({ ...m, isStreaming: false }));
      setCurrentTool(null);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setMessages(prev => [...prev, { id: nextId(), role: 'assistant', content: `Error: ${(err as Error).message}`, isMarkdown: false, isStreaming: false }]);
      }
    } finally {
      setStreaming(false);
      setCurrentTool(null);
      abortRef.current = null;
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(); }
  }

  function clearMessages() {
    abortRef.current?.abort();
    setMessages([]);
    setHitlState(null);
    setStreaming(false);
    cache.current.delete(selected.id);
  }

  async function handleHitl(approved: boolean) {
    if (!hitlState) return;
    const body: Record<string, unknown> = {
      workflow_id: hitlState.workflowId,
      run_id: hitlState.runId,
      session_id: hitlState.sessionId,
      approved,
    };
    if (hitlState.requiresInput && hitlInput.trim()) body['input'] = hitlInput.trim();
    setHitlState(null);
    setHitlInput('');
    try {
      await fetch(api('/api/workflow/continue'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch { /* ignore */ }
  }

  return (
    <>
      <div className={styles.messages}>
        {messages.map(msg => (
          <div key={msg.id} className={`${styles.message} ${styles[`msg_${msg.role.replace('-', '_')}`]}`}>
            {msg.isMarkdown
              ? <div className="md" dangerouslySetInnerHTML={{ __html: renderContent(msg) }} />
              : <span>{msg.content}</span>
            }
            {msg.isStreaming && <span className={styles.cursor} />}
            {!msg.isStreaming && msg.toolsCalled && msg.toolsCalled.length > 0 && (
              <div className={styles.toolsUsed}>
                {Array.from(new Set(msg.toolsCalled)).map(t => (
                  <span key={t} className="badge">
                    <span className="badge-label">Tool</span>
                    <span className="badge-value">{titleize(t)}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {currentTool && (
          <div className={styles.toolStatus}>
            <span className="badge">
              <span className="badge-label">Calling</span>
              <span className="badge-value">{titleize(currentTool)}</span>
            </span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {hitlState && (
        <div className={styles.hitlBar}>
          <span className={styles.hitlMsg}>{hitlState.message}</span>
          {hitlState.requiresInput && (
            <input className={styles.hitlInput} type="text" placeholder="Your response…"
              value={hitlInput} onChange={e => setHitlInput(e.target.value)} />
          )}
          <button className={styles.hitlApprove} onClick={() => void handleHitl(true)}>Approve</button>
          <button className={styles.hitlReject}  onClick={() => void handleHitl(false)}>Reject</button>
        </div>
      )}

      <div className={styles.inputRow}>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          placeholder={`Message ${selected.name}…`}
          value={input}
          onChange={e => { setInput(e.target.value); autoResize(); }}
          onKeyDown={handleKeyDown}
          disabled={streaming}
          rows={1}
        />
        <button className={styles.sendBtn} onClick={() => void send()} disabled={!input.trim() || streaming}>
          {streaming ? '…' : '↑'}
        </button>
        {messages.length > 0 && (
          <button className={styles.clearBtn} onClick={clearMessages} title="Clear chat">×</button>
        )}
      </div>
    </>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────────

interface AgentPanelProps {
  selected: SelectedAgent;
  config: AppConfig;
  userId: string;
  onClose: () => void;
}

export function AgentPanel({ selected, config, userId, onClose }: AgentPanelProps) {
  const [tab, setTab] = useState<PanelTab>('chat');

  useEffect(() => { setTab('chat'); }, [selected.id]);

  const icon = config.agent_icons[selected.id] ?? (selected.type === 'workflow' ? '⚡' : '🤖');
  const group = config.agent_groups.find(g => g.ids.includes(selected.id));
  const typeLabel = selected.type === 'workflow' ? 'Workflow' : (group?.label ?? 'Agent');
  const isWorkflow = selected.type === 'workflow';

  const tabs: { id: PanelTab; label: string }[] = [
    { id: 'chat',    label: 'Chat' },
    ...(!isWorkflow ? [{ id: 'config' as PanelTab, label: 'Description' }] : []),
  ];

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.icon}>{icon}</span>
        <div className={styles.headerInfo}>
          <span className={styles.agentName}>{selected.name}</span>
          <span className={styles.agentType}>{typeLabel}</span>
        </div>
        <button className={styles.closeBtn} onClick={onClose} title="Close">✕</button>
      </div>

      <div className={styles.tabBar}>
        {tabs.map(t => (
          <button
            key={t.id}
            className={`${styles.tabBtn} ${tab === t.id ? styles.tabBtnActive : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className={styles.body}>
        <div className={`${styles.pane} ${tab === 'chat' ? styles.paneActive : ''}`}>
          <ChatPane selected={selected} userId={userId} />
        </div>

        {tab === 'config' && (
          <div className={styles.paneScroll}>
            <DescriptionPane agentId={selected.id} />
          </div>
        )}
      </div>
    </div>
  );
}
