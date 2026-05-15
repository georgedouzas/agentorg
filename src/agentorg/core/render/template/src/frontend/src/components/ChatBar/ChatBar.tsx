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
      // AgentField exposes every spec runnable as `POST /reasoners/<name>` returning JSON `{output}`.
      // No SSE today, so we add the assistant message after the response lands.
      const res = await fetch(`${API_BASE}/reasoners/${encodeURIComponent(selected.id)}?user_id=${encodeURIComponent(userId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
        signal: abortCtrl.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const payload = await res.json() as { output?: unknown };
      const output = typeof payload.output === 'string'
        ? payload.output
        : JSON.stringify(payload.output ?? payload, null, 2);

      setMessages(prev => [...prev, {
        id: nextId(),
        role: 'assistant',
        content: output,
        isMarkdown: true,
        isStreaming: false,
      }]);
      // Skip the legacy SSE branch — it parses AgentOS events that AgentField doesn't emit.
      return;

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
            if (sid) sessionStorage.setItem(`session_${selected.id}`, sid);
          } else if (evType === 'RunContent' || evType === 'MessageDeltaContent') {
            const delta = (ev['content'] as string | undefined) ?? (ev['delta'] as string | undefined) ?? '';
            updateLastAssistant(m => ({ ...m, content: m.content + delta }));
          } else if (evType === 'ToolCallStarted') {
            const toolName = (ev['tool_name'] as string | undefined) ?? 'tool';
            const toolId = nextId();
            setMessages(prev => [...prev, {
              id: toolId,
              role: 'tool',
              content: `Calling ${toolName}…`,
            }]);
          } else if (evType === 'ToolCallCompleted') {
            const toolName = (ev['tool_name'] as string | undefined) ?? 'tool';
            setMessages(prev => {
              const idx = [...prev].reverse().findIndex(m => m.role === 'tool');
              if (idx === -1) return prev;
              const realIdx = prev.length - 1 - idx;
              const updated = [...prev];
              updated[realIdx] = { ...updated[realIdx]!, role: 'tool-done', content: `${toolName} done` };
              return updated;
            });
          } else if (evType === 'RunError') {
            const errMsg = (ev['error'] as string | undefined) ?? 'An error occurred';
            updateLastAssistant(m => ({ ...m, content: errMsg, isStreaming: false }));
          } else if (evType === 'WorkflowStarted') {
            const sid = ev['session_id'] as string | undefined;
            const rid = ev['run_id'] as string | undefined;
            if (sid) sessionStorage.setItem(`wf_session_${selected.id}`, sid);
            if (rid) sessionStorage.setItem(`wf_run_${selected.id}`, rid);
          } else if (evType === 'StepStarted') {
            const stepName = (ev['step_name'] as string | undefined) ?? 'Step';
            const stepId = nextId();
            setMessages(prev => [...prev, {
              id: stepId,
              role: 'step',
              content: `${stepName}…`,
            }]);
          } else if (evType === 'StepCompleted') {
            setMessages(prev => {
              const idx = [...prev].reverse().findIndex(m => m.role === 'step');
              if (idx === -1) return prev;
              const realIdx = prev.length - 1 - idx;
              const updated = [...prev];
              updated[realIdx] = { ...updated[realIdx]!, role: 'step-done' };
              return updated;
            });
          } else if (evType === 'ParallelExecutionStarted') {
            const stepId = nextId();
            setMessages(prev => [...prev, {
              id: stepId,
              role: 'step',
              content: 'Running parallel steps…',
            }]);
          } else if (evType === 'ParallelExecutionCompleted') {
            setMessages(prev => {
              const idx = [...prev].reverse().findIndex(m => m.role === 'step');
              if (idx === -1) return prev;
              const realIdx = prev.length - 1 - idx;
              const updated = [...prev];
              updated[realIdx] = { ...updated[realIdx]!, role: 'step-done' };
              return updated;
            });
          } else if (evType === 'StepPaused' || evType === 'StepOutputReview') {
            const wfSessionId = sessionStorage.getItem(`wf_session_${selected.id}`) ?? '';
            const wfRunId = sessionStorage.getItem(`wf_run_${selected.id}`) ?? '';
            const message = (ev['message'] as string | undefined) ?? 'Awaiting approval';
            setHitlState({
              workflowId: selected.id,
              runId: wfRunId,
              sessionId: wfSessionId,
              message,
              requiresInput: evType === 'StepOutputReview',
            });
          } else if (
            evType === 'WorkflowCompleted' ||
            evType === 'WorkflowError' ||
            evType === 'WorkflowCancelled' ||
            evType === 'RunCompleted'
          ) {
            // finalize
          }
        }
      }

      // Finalize streaming
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
