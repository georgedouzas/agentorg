import { useState, useRef, useEffect, useCallback, KeyboardEvent } from 'react';
import { marked } from 'marked';
import { API_BASE, api, apiFetch } from '../../api';
import type { AppConfig, ChatMessage, HitlState, SelectedAgent } from '../../types';
import styles from './AgentPanel.module.css';

type PanelTab = 'chat' | 'config';

// ── Description pane ─────────────────────────────────────────────────────────

interface OutOfScopeItem { topic: string; refer_to: string; }
interface OutputFormat { kind?: string; columns?: string[]; sections?: string[]; trailer?: string; }
interface CountRule { default?: number | string; rules?: { phrase: string; count: number | string }[]; }
interface SaveRule { tool?: string; name_pattern?: string; title_pattern?: string; note?: string; }

interface AgentInfo {
  agent_id: string;
  name: string;
  model_id: string;
  role?: string;
  in_scope?: string[];
  out_of_scope?: OutOfScopeItem[];
  workflow?: string[];
  output_format?: OutputFormat;
  count_rule?: CountRule;
  save_rule?: SaveRule;
  tools: string[];
  capabilities: Record<string, boolean>;
}

function DescriptionPane({ agentId }: { agentId: string }) {
  const [info, setInfo] = useState<AgentInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiFetch<AgentInfo>(`/api/agents/${encodeURIComponent(agentId)}/info`)
      .then(d => setInfo(d))
      .catch(() => setInfo(null))
      .finally(() => setLoading(false));
  }, [agentId]);

  if (loading) return <div className={styles.empty}>Loading…</div>;
  if (!info)   return <div className={styles.empty}>No information available for this agent.</div>;

  const fmt = (s: string) => s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const toolsLabel = info.tools.map(t => fmt(t).toUpperCase()).join(', ');
  const capsLabel = Object.keys(info.capabilities).map(c => c.toUpperCase()).join(', ');

  return (
    <div className={styles.descCard}>
      {info.role && (
        <Section title="Role"><p className={styles.descPara}>{info.role}</p></Section>
      )}

      {info.in_scope && info.in_scope.length > 0 && (
        <Section title="In scope">
          <ul className={styles.descList}>
            {info.in_scope.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </Section>
      )}

      {info.out_of_scope && info.out_of_scope.length > 0 && (
        <Section title="Out of scope · refer to">
          <ul className={styles.descList}>
            {info.out_of_scope.map((s, i) => (
              <li key={i}>{s.topic} → <strong>{s.refer_to}</strong></li>
            ))}
          </ul>
        </Section>
      )}

      {info.workflow && info.workflow.length > 0 && (
        <Section title="Workflow">
          <ol className={styles.descList}>
            {info.workflow.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
        </Section>
      )}

      {info.output_format && (
        <Section title="Output format">
          <p className={styles.descPara}>
            {info.output_format.kind === 'markdown_table' && info.output_format.columns && (
              <>Markdown table: <code>{info.output_format.columns.join(' | ')}</code>.{' '}</>
            )}
            {info.output_format.sections && (
              <>Sections (in order): {info.output_format.sections.join(', ')}.{' '}</>
            )}
            {info.output_format.trailer}
          </p>
        </Section>
      )}

      {info.count_rule && (
        <Section title="How many results">
          <ul className={styles.descList}>
            {info.count_rule.rules?.map((r, i) => (
              <li key={i}>{r.phrase} → <strong>{String(r.count)}</strong></li>
            ))}
            {info.count_rule.default !== undefined && (
              <li>(otherwise) → <strong>{String(info.count_rule.default)}</strong></li>
            )}
          </ul>
        </Section>
      )}

      {info.save_rule && (
        <Section title="Auto-save">
          <p className={styles.descPara}>
            Calls <code>{info.save_rule.tool}</code> at the end of each run.
            {info.save_rule.note && <> {info.save_rule.note}</>}
          </p>
        </Section>
      )}

      <div className={styles.badgeStack}>
        {info.model_id && <MetaBadge label="Model" value={info.model_id.toUpperCase()} />}
        {toolsLabel && <MetaBadge label="Tools" value={toolsLabel} />}
        {capsLabel && <MetaBadge label="Capabilities" value={capsLabel} />}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className={styles.descSection} style={{ borderTop: 'none', paddingTop: 0 }}>
      <h3 className={styles.descHeader}>{title}</h3>
      {children}
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
    if (selected.type === 'agent') {
      apiFetch<{ session_id: string | null; messages: { role: string; content: string }[] }>(
        `/api/agents/${encodeURIComponent(selected.id)}/history`,
      )
        .then(d => {
          if (d.session_id) localStorage.setItem(`session_${selected.id}`, d.session_id);
          if (d.messages.length === 0) return;
          const restored: ChatMessage[] = d.messages.map(m => ({
            id: nextId(),
            role: m.role as ChatMessage['role'],
            content: m.content,
            isMarkdown: m.role === 'assistant',
          }));
          setMessages(restored);
        })
        .catch(() => { /* ignore */ });
    }
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
      const isWorkflow = selected.type === 'workflow';
      const sessionKey = isWorkflow ? `wf_session_${selected.id}` : `session_${selected.id}`;
      const storedSession = localStorage.getItem(sessionKey) ?? undefined;

      const params = new URLSearchParams({ message: text, stream: 'true', stream_events: 'true' });
      if (storedSession) params.set('session_id', storedSession);
      params.set('user_id', userId);

      const endpoint = isWorkflow
        ? `/workflows/${selected.id}/runs`
        : `/agents/${selected.id}/runs`;

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params.toString(),
        signal: ctrl.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

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
          let ev: Record<string, unknown>;
          try { ev = JSON.parse(line.slice(6)) as Record<string, unknown>; } catch { continue; }
          const evType = ev['event'] as string | undefined;

          if (evType === 'RunStarted') {
            const sid = ev['session_id'] as string | undefined;
            if (sid) localStorage.setItem(`session_${selected.id}`, sid);
          } else if (evType === 'RunContent' || evType === 'MessageDeltaContent') {
            const delta = (ev['content'] as string | undefined) ?? (ev['delta'] as string | undefined) ?? '';
            if (!delta) continue;
            setCurrentTool(null);
            setMessages(prev => {
              const last = prev[prev.length - 1];
              if (last && last.role === 'assistant' && last.isStreaming) {
                const next = [...prev];
                next[prev.length - 1] = { ...last, content: last.content + delta };
                return next;
              }
              return [...prev, { id: nextId(), role: 'assistant', content: delta, isMarkdown: true, isStreaming: true }];
            });
          } else if (evType === 'ToolCallStarted') {
            const toolName = (ev['tool_name'] as string | undefined)
              ?? ((ev['tool'] as Record<string, unknown> | undefined)?.['tool_name'] as string | undefined)
              ?? ((ev['tool_call'] as Record<string, unknown> | undefined)?.['function'] as Record<string, unknown> | undefined)?.['name'] as string | undefined
              ?? 'tool';
            setCurrentTool(toolName);
            setMessages(prev => {
              const last = prev[prev.length - 1];
              if (last && last.role === 'assistant' && last.isStreaming) {
                const next = [...prev];
                next[prev.length - 1] = { ...last, toolsCalled: [...(last.toolsCalled ?? []), toolName] };
                return next;
              }
              return [...prev, { id: nextId(), role: 'assistant', content: '', isMarkdown: true, isStreaming: true, toolsCalled: [toolName] }];
            });
          } else if (evType === 'ToolCallCompleted') {
            // No-op: the tool indicator stays until the next tool starts or content arrives.
          } else if (evType === 'RunError') {
            const errMsg = (ev['error'] as string | undefined) ?? 'An error occurred';
            updateLastAssistant(m => ({ ...m, content: errMsg, isStreaming: false }));
          } else if (evType === 'WorkflowStarted') {
            const sid = ev['session_id'] as string | undefined;
            const rid = ev['run_id'] as string | undefined;
            if (sid) localStorage.setItem(`wf_session_${selected.id}`, sid);
            if (rid) localStorage.setItem(`wf_run_${selected.id}`, rid);
          } else if (evType === 'StepStarted') {
            const name = (ev['step_name'] as string | undefined) ?? 'Step';
            setMessages(prev => [...prev, { id: nextId(), role: 'step', content: `${name}…` }]);
          } else if (evType === 'StepCompleted') {
            setMessages(prev => {
              const idx = [...prev].reverse().findIndex(m => m.role === 'step');
              if (idx === -1) return prev;
              const real = prev.length - 1 - idx;
              const next = [...prev];
              next[real] = { ...next[real]!, role: 'step-done' };
              return next;
            });
          } else if (evType === 'ParallelExecutionStarted') {
            setMessages(prev => [...prev, { id: nextId(), role: 'step', content: 'Running parallel steps…' }]);
          } else if (evType === 'ParallelExecutionCompleted') {
            setMessages(prev => {
              const idx = [...prev].reverse().findIndex(m => m.role === 'step');
              if (idx === -1) return prev;
              const real = prev.length - 1 - idx;
              const next = [...prev];
              next[real] = { ...next[real]!, role: 'step-done' };
              return next;
            });
          } else if (evType === 'StepPaused' || evType === 'StepOutputReview') {
            const wfSession = localStorage.getItem(`wf_session_${selected.id}`) ?? '';
            const wfRun    = localStorage.getItem(`wf_run_${selected.id}`) ?? '';
            setHitlState({
              workflowId: selected.id,
              runId: wfRun,
              sessionId: wfSession,
              message: (ev['message'] as string | undefined) ?? 'Awaiting approval',
              requiresInput: evType === 'StepOutputReview',
            });
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
