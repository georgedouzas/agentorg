/* AgentOrg UI - live preview iframe + stage progress; the interview itself runs in LibreChat */

// ---------- handles ----------
const chatLink = document.getElementById('chat-link');
const stageBar = document.getElementById('stage-bar');
const previewFrame = document.getElementById('preview-frame');
const previewPlaceholder = document.getElementById('preview-placeholder');
const previewMessage = document.getElementById('preview-message');
const previewSub = document.getElementById('preview-sub');

// ---------- placeholder detection ----------
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

const fetchChatUrl = async () => {
  try {
    const r = await fetch('/api/chat-app');
    const data = await r.json();
    if (data.url) chatLink.href = data.url;
  } catch { /* keep the default address */ }
};

// ---------- wiring ----------
// The interview happens in LibreChat, so poll the draft to keep the stage bar current.
const SPEC_POLL_MS = 2000;
fetchChatUrl();
fetchSpec();
setInterval(fetchSpec, SPEC_POLL_MS);
startPreviewPolling();
