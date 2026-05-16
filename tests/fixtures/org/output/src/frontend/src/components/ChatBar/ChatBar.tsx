import { useState, useRef, useEffect, useCallback, KeyboardEvent } from 'react';
import { marked } from 'marked';
import { API_BASE, api } from '../../api';
import type { ChatMessage, HitlState, SelectedAgent } from '../../types';
import styles from './ChatBar.module.css';

interface CachedAgentState {
  messages: ChatMessage[];
  hitlState: HitlState | null;
}

interface ChatBarProps {
  selected: SelectedAgent | null;
  userId: string;
}

let msgIdCounter = 0;
function nextId(): string {
  return `m${++msgIdCounter}`;
}

function renderContent(msg: ChatMessage): string {
  if (msg.isMarkdown) {
    return marked.parse(msg.content) as string;
  }
  return msg.content.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export function ChatBar({ selected, userId }: ChatBarProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [hitlState, setHitlState] = useState<HitlState | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [input, setInput] = useState('');
  const [hitlInput, setHitlInput] = useState('');

  const cache = useRef<Map<string, CachedAgentState>>(new Map());
  const prevSelected = useRef<SelectedAgent | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Save/restore per-agent state on selection change
  useEffect(() => {
    const prev = prevSelected.current;
    if (prev) {
      cache.current.set(prev.id, {
        messages,
        hitlState,
      });
    }
    prevSelected.current = selected;
    if (selected) {
      const cached = cache.current.get(selected.id);
      setMessages(cached?.messages ?? []);
      setHitlState(cached?.hitlState ?? null);
    } else {
      setMessages([]);
      setHitlState(null);
    }
    setInput('');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  function autoResize() {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  }

  const updateLastAssistant = useCallback((updater: (prev: ChatMessage) => ChatMessage) => {
    setMessages(prev => {
      const idx = [...prev].reverse().findIndex(m => m.role === 'assistant');
      if (idx === -1) return prev;
      const realIdx = prev.length - 1 - idx;
      const updated = [...prev];
      updated[realIdx] = updater(updated[realIdx]!);
      return updated;
    });
  }, []);

  async function send() {
    if (!selected || !input.trim() || streaming) return;
    const text = input.trim();
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';

    const userMsg: ChatMessage = { id: nextId(), role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setStreaming(true);

    const abortCtrl = new AbortController();
    abortRef.current = abortCtrl;

    try {
      // Persist a stable session id per (user, agent) so agno's memory can scope chat history
      // for this conversation; a refresh of the same tab continues the same session.
      const sessionKey = `session_${userId}_${selected.id}`;
      let sessionId = sessionStorage.getItem(sessionKey);
      if (!sessionId) {
        sessionId = `${selected.id}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
        sessionStorage.setItem(sessionKey, sessionId);
      }

      // Stream agno events from the org's reasoner via SSE: tokens land into the assistant
      // bubble live, <thinking>...</thinking> traces are hidden on the fly.
      const res = await fetch(`${API_BASE}/api/v1/reasoners/${encodeURIComponent(selected.id)}/stream?user_id=${encodeURIComponent(userId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId, user_id: userId }),
        signal: abortCtrl.signal,
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
          let ev: { event?: string; content?: string; error?: string };
          try { ev = JSON.parse(dataLine.slice(6)) as typeof ev; } catch { continue; }
          if (ev.event === 'RunContent' && ev.content) {
            raw += ev.content;
            const display = stripThinking(raw);
            updateLastAssistant(m => ({ ...m, content: display }));
          } else if (ev.event === 'RunCompleted' && ev.content) {
            raw = ev.content;
            updateLastAssistant(m => ({ ...m, content: stripThinking(raw), isStreaming: false }));
          } else if (ev.event === 'RunError') {
            updateLastAssistant(m => ({ ...m, content: ev.error || 'An error occurred', isStreaming: false }));
          }
        }
      }
      updateLastAssistant(m => ({ ...m, isStreaming: false }));
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setMessages(prev => [...prev, {
          id: nextId(),
          role: 'assistant',
          content: `Error: ${(err as Error).message}`,
          isMarkdown: false,
          isStreaming: false,
        }]);
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  function clearMessages() {
    abortRef.current?.abort();
    setMessages([]);
    setHitlState(null);
    setStreaming(false);
    if (selected) {
      cache.current.delete(selected.id);
    }
  }

  async function handleHitlContinue(approved: boolean) {
    if (!hitlState) return;
    const body: Record<string, unknown> = {
      workflow_id: hitlState.workflowId,
      run_id: hitlState.runId,
      session_id: hitlState.sessionId,
      approved,
    };
    if (hitlState.requiresInput && hitlInput.trim()) {
      body['input'] = hitlInput.trim();
    }
    setHitlState(null);
    setHitlInput('');
    try {
      await fetch(api('/api/workflow/continue'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch {
      // ignore
    }
  }

  const placeholder = selected
    ? `Message ${selected.name}…`
    : 'Select an agent or workflow to start chatting';

  return (
    <div className={styles.chatBar}>
      {messages.length > 0 && (
        <div className={styles.messages}>
          {messages.map(msg => (
            <div
              key={msg.id}
              className={`${styles.message} ${styles[`msg_${msg.role.replace('-', '_')}`]}`}
            >
              {msg.isMarkdown ? (
                <div
                  className="md"
                  dangerouslySetInnerHTML={{ __html: renderContent(msg) }}
                />
              ) : (
                <span>{msg.content}</span>
              )}
              {msg.isStreaming && <span className={styles.cursor} />}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      )}

      {hitlState && (
        <div className={styles.hitlBar}>
          <span className={styles.hitlMsg}>{hitlState.message}</span>
          {hitlState.requiresInput && (
            <input
              className={styles.hitlInput}
              type="text"
              placeholder="Your response…"
              value={hitlInput}
              onChange={e => setHitlInput(e.target.value)}
            />
          )}
          <button className={styles.hitlApprove} onClick={() => void handleHitlContinue(true)}>
            Approve
          </button>
          <button className={styles.hitlReject} onClick={() => void handleHitlContinue(false)}>
            Reject
          </button>
        </div>
      )}

      <div className={styles.inputRow}>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          placeholder={placeholder}
          value={input}
          onChange={e => { setInput(e.target.value); autoResize(); }}
          onKeyDown={handleKeyDown}
          disabled={!selected || streaming}
          rows={1}
        />
        <button
          className={styles.sendBtn}
          onClick={() => void send()}
          disabled={!selected || !input.trim() || streaming}
        >
          {streaming ? '…' : '↑'}
        </button>
        {messages.length > 0 && (
          <button className={styles.clearBtn} onClick={clearMessages} title="Clear chat">
            ×
          </button>
        )}
      </div>
    </div>
  );
}
