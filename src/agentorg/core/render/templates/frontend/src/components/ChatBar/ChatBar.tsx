import { useState, useRef, useEffect, useCallback, KeyboardEvent } from 'react';
import { marked } from 'marked';
import { decideApproval, postRun, readRunStream } from '../../api';
import type { ChatMessage, HitlState, SelectedAgent } from '../../types';
import { applyRunEvent, finalText } from '../../chatEvents';
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
      // A stable session id per (user, agent) keeps the agent's conversation memory across turns.
      const sessionKey = `session_${userId}_${selected.id}`;
      let sessionId = sessionStorage.getItem(sessionKey);
      if (!sessionId) {
        sessionId = `${selected.id}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
        sessionStorage.setItem(sessionKey, sessionId);
      }

      const res = await postRun(selected.id, userId, { message: text, session_id: sessionId, user_id: userId }, abortCtrl.signal);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      setMessages(prev => [...prev, { id: nextId(), role: 'assistant', content: '', isMarkdown: true, isStreaming: true }]);
      let streamed = '';
      await readRunStream(res, (name, data) => applyRunEvent(name, data, {
        appendText: chunk => {
          streamed = streamed ? `${streamed}\n\n${chunk}` : chunk;
          const shown = streamed;
          updateLastAssistant(m => ({ ...m, content: shown }));
        },
        toolStarted: name => { updateLastAssistant(m => ({ ...m, toolsCalled: [...(m.toolsCalled ?? []), name] })); },
        toolFinished: () => undefined,
        approvalRequested: (approvalId, tool) => setHitlState({ approvalId, message: `Waiting for approval to run ${tool}` }),
        approvalDecided: () => setHitlState(null),
        finish: (status, output, reason) => {
          const shown = finalText(streamed, status, output, reason);
          updateLastAssistant(m => ({ ...m, content: shown, isStreaming: false }));
        },
      }));
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
    const { approvalId } = hitlState;
    const comment = hitlInput.trim();
    setHitlState(null);
    setHitlInput('');
    try { await decideApproval(approvalId, userId, approved, comment); } catch { /* the inbox shows it is still pending */ }
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
          {(
            <input
              className={styles.hitlInput}
              type="text"
              placeholder="Comment (sent with a rejection)…"
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
