/* AgentOrg UI - canvas iframe + draggable popup chat + stage progress */

// ---------- handles ----------
const chatLog = document.getElementById('chat-log');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
const status = document.getElementById('status');
const resetBtn = document.getElementById('reset-btn');
const stageBar = document.getElementById('stage-bar');
const previewFrame = document.getElementById('preview-frame');
const previewPlaceholder = document.getElementById('preview-placeholder');
const previewMessage = document.getElementById('preview-message');
const previewSub = document.getElementById('preview-sub');
const chatPopup = document.getElementById('chat-popup');
const chatPopupHeader = document.getElementById('chat-popup-header');

// ---------- placeholder detection (kept; still used by chat empty hero etc) ----------
const PLACEHOLDER_VALUES = new Set([
  'Not set yet', 'Untitled org', 'untitled-org', 'untitled_org',
  'you@example.com', '🛠', 'You',
  'A new agent organisation in progress.',
  'Nothing here yet', 'Your org is taking shape — keep chatting with AgentOrg.', '✨',
  'No knowledge entries yet.',
  // Legacy values - keep so old draft files still register as placeholders.
  'TODO', 'My Org', 'my-org', 'my_org', 'author@example.com', 'robot',
]);
const isPlaceholder = (v) => typeof v === 'string' && PLACEHOLDER_VALUES.has(v);

// ---------- stage progress bar ----------
const FALLBACK_STAGES = [
  { id: 'discover',  label: 'Discover'  },
  { id: 'configure', label: 'Configure' },
  { id: 'build',     label: 'Build'     },
  { id: 'refine',    label: 'Refine'    },
  { id: 'handoff',   label: 'Handoff'   },
];

let lastStageSummary = {
  stage: 'discover',
  stage_label: 'Discover',
  stages: FALLBACK_STAGES.map(s => s.id),
  next_enabled: false,
  next_blockers: [],
};

// ---------- DOM helpers ----------
const el = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'className') node.className = v;
    else if (k === 'innerHTML') node.innerHTML = v;
    else node.setAttribute(k, v);
  }
  for (const child of children.flat()) {
    if (child == null) continue;
    node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  return node;
};

const renderMarkdown = (text) => {
  if (window.marked) return window.marked.parse(text, { breaks: true });
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;');
};

const labelFor = (id) => id.charAt(0).toUpperCase() + id.slice(1);

// ---------- stage bar render ----------
const renderStageBar = (summary) => {
  stageBar.innerHTML = '';
  const stages = summary?.stages?.length
    ? summary.stages.map(id => ({ id, label: labelFor(id) }))
    : FALLBACK_STAGES;
  const currentStage = summary?.stage || stages[0].id;
  const currentIdx = stages.findIndex(s => s.id === currentStage);
  stages.forEach((s, i) => {
    const cls = i < currentIdx ? 'done' : i === currentIdx ? 'current' : '';
    stageBar.appendChild(el('div', { className: `stage ${cls}`.trim() },
      el('div', { className: 'stage-dot' }, String(i + 1)),
      el('div', { className: 'stage-label' }, s.label),
    ));
    if (i < stages.length - 1) {
      stageBar.appendChild(el('div', { className: `stage-line ${i < currentIdx ? 'done' : ''}`.trim() }));
    }
  });
};

const applyStageSummary = (summary) => {
  // No Next button to wire up - the master agent owns stage transitions via the
  // `advance_to_next_stage` tool after user confirmation in chat. The stage bar still
  // updates to show progress.
  lastStageSummary = summary || lastStageSummary;
  renderStageBar(lastStageSummary);
};

// ---------- chat rendering ----------
const showEmptyHero = () => {
  chatLog.innerHTML = '';
  chatLog.appendChild(el('div', { className: 'empty-hero' },
    el('div', { className: 'lead' }, "Hi, I'm AgentOrg."),
    el('div', {}, 'Tell me what you want to build and watch your organziation take shape as we go.'),
  ));
};

const appendMessage = (role, content) => {
  if (chatLog.querySelector('.empty-hero')) chatLog.innerHTML = '';
  const roleLabel = role === 'user' ? 'You' : 'Master';
  const body = role === 'master'
    ? el('div', { innerHTML: renderMarkdown(content) })
    : el('div', {}, content);
  const bubble = el('div', { className: `bubble ${role}` },
    el('div', { className: 'role' }, roleLabel),
    body,
  );
  chatLog.appendChild(bubble);
  if (role === 'user') bubble.scrollIntoView({ block: 'start', behavior: 'smooth' });
};

const appendToolCalls = (calls) => {
  if (!calls?.length) return;
  const bubble = el('div', { className: 'bubble tool-calls' }, `🛠  ${calls.join('  ·  ')}`);
  chatLog.appendChild(bubble);
};

const setBusy = (busy) => {
  chatSend.disabled = busy;
  chatInput.disabled = busy;
  if (busy) {
    status.innerHTML = '';
    status.appendChild(el('span', { className: 'dots' },
      el('span', {}), el('span', {}), el('span', {}),
    ));
    status.appendChild(document.createTextNode(' Thinking…'));
  } else {
    status.textContent = '';
  }
};

// ---------- preview placeholder ----------
const updatePreviewPlaceholder = (spec) => {
  if (!spec) return;
  const orgName = isPlaceholder(spec.org?.name) ? 'your org' : spec.org.name;
  if (!previewFrame.src) previewMessage.textContent = `Preview for ${orgName} is starting…`;
};

// ---------- preview status polling ----------
//
// We keep polling at a low cadence even after the iframe has loaded, so that if the
// master UI restarts (and the rendered org's subprocesses get fresh ports), the iframe
// auto-swaps to the new URL. Without this, the browser keeps a stale iframe src pointed
// at a dead port and shows "connection refused" until the user does a full reload.
const POLL_FAST_MS = 1200;   // before the preview is ready
const POLL_SLOW_MS = 10000;  // after - just enough to catch URL changes on restart
let previewPollHandle = null;
let previewState = 'unknown';
let previewCurrentUrl = null;

const swapToIframe = (url) => {
  if (previewCurrentUrl === url) return;
  previewCurrentUrl = url;
  previewFrame.src = url;
  previewFrame.hidden = false;
  previewPlaceholder.style.display = 'none';
};
const showPreviewError = (detail) => {
  previewMessage.textContent = 'Preview failed to start';
  previewSub.textContent = detail || 'Check the master UI logs for details.';
  previewPlaceholder.style.display = 'flex';
  previewFrame.hidden = true;
};
const showPreviewDisabled = () => {
  previewMessage.textContent = 'Preview is disabled';
  previewSub.textContent = 'The master UI was started without the live preview subprocess.';
};

const setPollCadence = (ms) => {
  if (previewPollHandle) clearInterval(previewPollHandle);
  previewPollHandle = setInterval(pollPreview, ms);
};

async function pollPreview() {
  try {
    const r = await fetch('/api/preview');
    const data = await r.json();
    const wasReady = previewState === 'ready';
    previewState = data.status;
    if (data.status === 'ready' && data.frontend_url) {
      swapToIframe(data.frontend_url);
      if (!wasReady) setPollCadence(POLL_SLOW_MS);
    } else if (data.status === 'error') {
      showPreviewError(data.detail);
      if (previewPollHandle) { clearInterval(previewPollHandle); previewPollHandle = null; }
    } else if (data.status === 'disabled') {
      showPreviewDisabled();
      if (previewPollHandle) { clearInterval(previewPollHandle); previewPollHandle = null; }
    } else if (wasReady) {
      // Status went backwards (master UI restart, preview re-booting). Switch back to
      // fast polling so we catch the new URL as soon as it's announced.
      setPollCadence(POLL_FAST_MS);
    }
  } catch (e) {
    console.warn('preview poll failed', e);
  }
}

const startPreviewPolling = () => {
  pollPreview();
  setPollCadence(POLL_FAST_MS);
};

// ---------- popup chat: drag-to-move (always visible, no hide/show) ----------
const POPUP_POS_KEY = 'agentorg.chat.popup.pos';

const savePopupPos = () => {
  const rect = chatPopup.getBoundingClientRect();
  localStorage.setItem(POPUP_POS_KEY, JSON.stringify({ left: rect.left, top: rect.top }));
};
const restorePopupPos = () => {
  try {
    const pos = JSON.parse(localStorage.getItem(POPUP_POS_KEY) || 'null');
    if (pos && Number.isFinite(pos.left) && Number.isFinite(pos.top)) {
      // Clamp the saved position to the current viewport so a stale drag from a
      // larger window doesn't park the popup off-screen.
      const w = chatPopup.offsetWidth || 340;
      const h = chatPopup.offsetHeight || 440;
      const maxLeft = Math.max(4, window.innerWidth - w - 4);
      const maxTop = Math.max(4, window.innerHeight - h - 4);
      const left = Math.max(4, Math.min(maxLeft, pos.left));
      const top = Math.max(4, Math.min(maxTop, pos.top));
      chatPopup.style.right = 'auto';
      chatPopup.style.bottom = 'auto';
      chatPopup.style.left = `${left}px`;
      chatPopup.style.top = `${top}px`;
    }
  } catch { /* ignore */ }
};

// Drag handling
let dragState = null;
chatPopupHeader.addEventListener('pointerdown', (ev) => {
  if (ev.target.closest('.chat-popup-btn')) return;
  const rect = chatPopup.getBoundingClientRect();
  dragState = {
    offsetX: ev.clientX - rect.left,
    offsetY: ev.clientY - rect.top,
    pointerId: ev.pointerId,
  };
  chatPopupHeader.setPointerCapture(ev.pointerId);
  // Switch to absolute positioning if not already.
  chatPopup.style.right = 'auto';
  chatPopup.style.bottom = 'auto';
});
chatPopupHeader.addEventListener('pointermove', (ev) => {
  if (!dragState || ev.pointerId !== dragState.pointerId) return;
  const maxLeft = window.innerWidth - chatPopup.offsetWidth - 4;
  const maxTop = window.innerHeight - chatPopup.offsetHeight - 4;
  const left = Math.max(4, Math.min(maxLeft, ev.clientX - dragState.offsetX));
  const top = Math.max(4, Math.min(maxTop, ev.clientY - dragState.offsetY));
  chatPopup.style.left = `${left}px`;
  chatPopup.style.top = `${top}px`;
});
chatPopupHeader.addEventListener('pointerup', (ev) => {
  if (!dragState || ev.pointerId !== dragState.pointerId) return;
  chatPopupHeader.releasePointerCapture(ev.pointerId);
  savePopupPos();
  dragState = null;
});

// Restore position on load
restorePopupPos();

// ---------- API ----------
const fetchSpec = async () => {
  try {
    const r = await fetch('/api/spec');
    const data = await r.json();
    applyStageSummary(data.stage_summary);
    updatePreviewPlaceholder(data.spec);
  } catch (e) {
    console.error('failed to fetch spec', e);
  }
};

const sendChat = async (message) => {
  const r = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  let body = null;
  try { body = await r.json(); } catch { /* keep null */ }
  if (!r.ok) {
    const detail = body?.detail;
    const err = new Error(typeof detail === 'string' ? detail : `Chat failed (HTTP ${r.status}).`);
    err.transient = r.status === 503;
    throw err;
  }
  return body;
};

const doReset = async () => {
  if (!confirm('Start over from scratch? The current draft will be discarded.')) return;
  try {
    await fetch('/api/reset', { method: 'POST' });
    showEmptyHero();
    // The preview URL didn't change (same subprocesses) but the rendered spec did, so the
    // iframe is now showing stale React state. Force a reload by re-assigning the src.
    if (previewCurrentUrl) {
      previewFrame.src = previewCurrentUrl;
    }
    await fetchSpec();
    chatInput.focus();
  } catch (e) {
    appendMessage('master', `**Error resetting:** ${e.message}`);
  }
};

// ---------- wiring ----------
chatForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const msg = chatInput.value.trim();
  if (!msg) return;
  chatInput.value = '';
  appendMessage('user', msg);
  setBusy(true);
  try {
    const { response, tool_calls } = await sendChat(msg);
    appendToolCalls(tool_calls);
    appendMessage('master', response || '(no reply)');
    await fetchSpec();
  } catch (e) {
    const hint = e.transient
      ? "\n\n_Your message is still in the input — press Enter to retry once the model comes back._"
      : '';
    appendMessage('master', `**Error:** ${e.message}${hint}`);
    chatInput.value = msg;
  } finally {
    setBusy(false);
    chatInput.focus();
  }
});

chatInput.addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter' && !ev.shiftKey) {
    ev.preventDefault();
    chatForm.requestSubmit();
  }
});

resetBtn.addEventListener('click', doReset);

showEmptyHero();
fetchSpec();
startPreviewPolling();
chatInput.focus();
