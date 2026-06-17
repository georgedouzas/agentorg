/* AgentOrg UI - chat client + live spec view */

const chatLog = document.getElementById('chat-log');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
const status = document.getElementById('status');
const specRoot = document.getElementById('spec-root');
const resetBtn = document.getElementById('reset-btn');
const createBtn = document.getElementById('create-btn');
const stageBar = document.getElementById('stage-bar');

const STAGES = [
  { id: 'discover', label: 'Discover' },
  { id: 'propose',  label: 'Propose'  },
  { id: 'build',    label: 'Build'    },
  { id: 'audit',    label: 'Audit'    },
  { id: 'review',   label: 'Review'   },
];
const createDialog = document.getElementById('create-dialog');
const createForm = document.getElementById('create-form');
const createOrgName = document.getElementById('create-org-name');
const createZipName = document.getElementById('create-zip-name');
const createStatus = document.getElementById('create-status');
const createCancel = document.getElementById('create-cancel');
const createConfirm = document.getElementById('create-confirm');

let lastReadiness = { ready: false, blockers: [], org_slug: '' };
let lastOrgName = '';

const PLACEHOLDER_VALUES = new Set(['TODO', 'My Org', 'my-org', 'my_org', 'author@example.com', 'robot']);
const isPlaceholder = (v) => typeof v === 'string' && PLACEHOLDER_VALUES.has(v);

// ---------- helpers ----------

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

const chip = (text, cls = '') => el('span', { className: `chip ${cls}` }, text);

const renderMarkdown = (text) => {
  if (window.marked) return window.marked.parse(text, { breaks: true });
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;');
};

// ---------- chat rendering ----------

const showEmptyHero = () => {
  chatLog.innerHTML = '';
  chatLog.appendChild(el('div', { className: 'empty-hero' },
    el('div', { className: 'lead' }, "Hi, I'm AgentOrg."),
    el('div', {}, 'Describe what your organization should do and I will sketch a plan, build it out, and write the spec.'),
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
  // Pin the user's question to the top of the visible chat area so a long master reply
  // does not drag the viewport away. Master + tool-call bubbles append below without
  // scrolling - the user reads top-down and scrolls themselves.
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
    status.appendChild(document.createTextNode(' thinking…'));
  } else {
    status.textContent = '';
  }
};

// ---------- spec rendering ----------

const valueOrPlaceholder = (v) => {
  if (v == null || v === '' || isPlaceholder(v)) return el('span', { className: 'placeholder' }, '—');
  return document.createTextNode(String(v));
};

const renderOrgCard = (org) => {
  const card = el('div', { className: 'card org-card' });
  card.appendChild(el('h3', {},
    isPlaceholder(org.name) ? el('span', { className: 'placeholder' }, '—') : org.name,
    el('span', { className: 'id' }, isPlaceholder(org.slug) ? '—' : (org.slug || '—')),
  ));
  if (org.description) card.appendChild(el('div', { className: 'role-line' }, valueOrPlaceholder(org.description)));
  const meta = el('div', { className: 'org-meta' });
  const cell = (label, value) => {
    meta.appendChild(el('span', { className: 'k' }, label));
    meta.appendChild(el('span', {}, valueOrPlaceholder(value)));
  };
  cell('package', org.package_name);
  cell('visibility', org.visibility);
  cell('admin', org.admin_name);
  cell('email', org.admin_email);
  cell('repository', org.repository);
  card.appendChild(meta);
  return card;
};

const renderAgentCard = (agent) => {
  const card = el('div', { className: 'card' });
  card.appendChild(el('h3', {},
    agent.name || '(unnamed agent)',
    el('span', { className: 'id' }, agent.agent_id),
  ));
  if (agent.role) card.appendChild(el('div', { className: 'role-line' }, agent.role));

  if (agent.tools?.length || agent.skills?.length) {
    const row = el('div', { className: 'row' });
    if (agent.tools?.length) {
      row.appendChild(el('span', { className: 'label' }, 'tools'));
      const chips = el('div', { className: 'chips' });
      agent.tools.forEach(t => chips.appendChild(chip(t)));
      row.appendChild(chips);
    }
    if (agent.skills?.length) {
      row.appendChild(el('span', { className: 'label' }, 'skills'));
      const chips = el('div', { className: 'chips' });
      agent.skills.forEach(s => chips.appendChild(chip(s, 'skill')));
      row.appendChild(chips);
    }
    card.appendChild(row);
  }

  if (agent.in_scope?.length) {
    card.appendChild(el('span', { className: 'label' }, 'in scope'));
    const ul = el('ul', { className: 'list-tight' });
    agent.in_scope.forEach(s => ul.appendChild(el('li', {}, s)));
    card.appendChild(ul);
  }

  if (agent.workflow?.length) {
    card.appendChild(el('span', { className: 'label' }, 'workflow'));
    const steps = el('ol', { className: 'steps' });
    agent.workflow.forEach(s => steps.appendChild(el('li', {}, s)));
    card.appendChild(steps);
  }
  return card;
};

const renderTeamCard = (team) => {
  const card = el('div', { className: 'card' });
  card.appendChild(el('h3', {},
    team.name || '(unnamed team)',
    el('span', { className: 'id' }, team.team_id),
  ));
  if (team.role) card.appendChild(el('div', { className: 'role-line' }, team.role));
  if (team.member_ids?.length) {
    card.appendChild(el('span', { className: 'label' }, 'members'));
    const chips = el('div', { className: 'chips' });
    team.member_ids.forEach(m => chips.appendChild(chip(m, 'member')));
    card.appendChild(chips);
  }
  if (team.workflow?.length) {
    card.appendChild(el('span', { className: 'label' }, 'coordination'));
    const steps = el('ol', { className: 'steps' });
    team.workflow.forEach(s => steps.appendChild(el('li', {}, s)));
    card.appendChild(steps);
  }
  return card;
};

const renderWorkflowCard = (wf) => {
  const card = el('div', { className: 'card' });
  card.appendChild(el('h3', {},
    wf.name || '(unnamed workflow)',
    el('span', { className: 'id' }, wf.workflow_id),
  ));
  if (wf.description) card.appendChild(el('div', { className: 'role-line' }, wf.description));
  if (wf.steps?.length) {
    card.appendChild(el('span', { className: 'label' }, 'steps'));
    const steps = el('ol', { className: 'steps' });
    wf.steps.forEach(step => {
      const li = el('li', {}, step.name + ' ');
      li.appendChild(chip(step.agent_id, 'member'));
      if (step.requires_output_review) li.appendChild(chip('review', 'tag'));
      steps.appendChild(li);
    });
    card.appendChild(steps);
  }
  return card;
};

const renderKnowledgeSection = (knowledge) => {
  const wrap = document.createDocumentFragment();
  if (knowledge.types?.length) {
    knowledge.types.forEach(t => {
      const card = el('div', { className: 'card' });
      card.appendChild(el('h3', {},
        t.label || t.id,
        el('span', { className: 'id' }, t.id),
      ));
      if (t.metadata_fields?.length) {
        const chips = el('div', { className: 'chips' });
        t.metadata_fields.forEach(f => chips.appendChild(chip(`${f.name}:${f.type}`, 'tag')));
        card.appendChild(chips);
      }
      wrap.appendChild(card);
    });
  }
  if (knowledge.principles?.sections?.length) {
    knowledge.principles.sections.forEach(s => {
      const card = el('div', { className: 'card' });
      card.appendChild(el('h3', {}, s.title || s.id, el('span', { className: 'id' }, 'principle')));
      const body = el('div', { className: 'role-line', innerHTML: renderMarkdown(s.body || '') });
      card.appendChild(body);
      wrap.appendChild(card);
    });
  }
  return wrap;
};

const renderParameter = (p) => {
  const card = el('div', { className: 'card' });
  card.appendChild(el('h3', {}, p.label || p.name, el('span', { className: 'id' }, `${p.type} = ${JSON.stringify(p.default)}`)));
  return card;
};

const renderSetupStep = (step) => {
  const card = el('div', { className: 'card setup-card' });
  card.appendChild(el('h3', {},
    step.title || step.id,
    el('span', { className: 'id' }, step.id),
  ));
  if (step.description) {
    const body = el('div', { className: 'role-line', innerHTML: renderMarkdown(step.description) });
    card.appendChild(body);
  }
  if (step.variables?.length) {
    card.appendChild(el('span', { className: 'label' }, 'env vars'));
    const chips = el('div', { className: 'chips' });
    step.variables.forEach(v => chips.appendChild(chip(v, 'env')));
    card.appendChild(chips);
  }
  return card;
};

const renderEnvVar = (envVar, required) => {
  const card = el('div', { className: 'card env-card' });
  card.appendChild(el('h3', {},
    envVar.name,
    el('span', { className: 'id' }, required ? 'required' : 'optional'),
  ));
  if (envVar.description) card.appendChild(el('div', { className: 'role-line' }, envVar.description));
  return card;
};

// Extract env-var names referenced by `os.environ['VAR']` / `os.environ["VAR"]` /
// `os.getenv('VAR'...)`. Distinguishes runs-now from setup-debt custom tools at a glance.
const extractEnvVars = (source) => {
  const vars = new Set();
  const patterns = [
    /os\.environ\[['"]([A-Z_][A-Z0-9_]*)['"]\]/g,
    /os\.environ\.get\(\s*['"]([A-Z_][A-Z0-9_]*)['"]/g,
    /os\.getenv\(\s*['"]([A-Z_][A-Z0-9_]*)['"]/g,
  ];
  for (const re of patterns) {
    let m;
    while ((m = re.exec(source)) !== null) vars.add(m[1]);
  }
  return [...vars];
};

const renderCustomTool = (t) => {
  const card = el('div', { className: 'card' });
  const envVars = extractEnvVars(t.source);
  const status = envVars.length ? 'setup-debt' : 'runs-now';
  card.appendChild(el('h3', {},
    t.name,
    el('span', { className: 'id' }, 'custom tool'),
    el('span', { className: `tool-status ${status}` }, status),
  ));
  if (envVars.length) {
    card.appendChild(el('span', { className: 'label' }, 'needs env vars'));
    const chips = el('div', { className: 'chips' });
    envVars.forEach(v => chips.appendChild(chip(v, 'env')));
    card.appendChild(chips);
  }
  const details = el('details', { className: 'collapsible' },
    el('summary', {}, 'source'),
    el('pre', {}, t.source),
  );
  card.appendChild(details);
  return card;
};

const renderCustomSkill = (s) => {
  const card = el('div', { className: 'card' });
  card.appendChild(el('h3', {}, s.name, el('span', { className: 'id' }, 'custom skill')));
  const details = el('details', { className: 'collapsible' },
    el('summary', {}, 'SKILL.md'),
    el('pre', {}, s.skill_md),
  );
  card.appendChild(details);
  return card;
};

const sectionTitle = (title, count) => {
  const h = el('div', { className: 'section-title' }, title);
  if (count != null) h.appendChild(el('span', { className: 'count' }, String(count)));
  return h;
};

const renderStageBar = (currentStage) => {
  stageBar.innerHTML = '';
  const currentIdx = STAGES.findIndex(s => s.id === currentStage);
  STAGES.forEach((s, i) => {
    const status = i < currentIdx ? 'done' : i === currentIdx ? 'current' : '';
    stageBar.appendChild(el('div', { className: `stage ${status}`.trim() },
      el('div', { className: 'stage-dot' }, String(i + 1)),
      el('div', { className: 'stage-label' }, s.label),
    ));
    if (i < STAGES.length - 1) {
      stageBar.appendChild(el('div', { className: `stage-line ${i < currentIdx ? 'done' : ''}`.trim() }));
    }
  });
};

const applyReadiness = (readiness, orgName) => {
  lastReadiness = readiness || { ready: false, blockers: [], org_slug: '', stage: 'discover' };
  lastOrgName = orgName || '';
  createBtn.disabled = !lastReadiness.ready;
  if (lastReadiness.ready) {
    createBtn.title = 'Render the project tree';
  } else if (lastReadiness.blockers?.length) {
    createBtn.title = 'Cannot create yet:\n• ' + lastReadiness.blockers.join('\n• ');
  } else {
    createBtn.title = 'Not ready yet';
  }
  renderStageBar(lastReadiness.stage || 'discover');
};

const renderSpec = (payload) => {
  specRoot.innerHTML = '';
  const { spec, custom_tools, custom_skills, readiness } = payload;
  applyReadiness(readiness, isPlaceholder(spec.org.name) ? '' : spec.org.name);

  const header = el('div', { className: 'spec-header' });
  const unset = isPlaceholder(spec.org.name);
  header.appendChild(el('div', { className: `org-name${unset ? ' unset' : ''}` },
    unset ? 'No name provided yet' : spec.org.name,
  ));
  specRoot.appendChild(header);

  specRoot.appendChild(renderOrgCard(spec.org));

  // agents
  specRoot.appendChild(sectionTitle('agents', spec.ai.agents.length));
  if (spec.ai.agents.length) spec.ai.agents.forEach(a => specRoot.appendChild(renderAgentCard(a)));
  else specRoot.appendChild(el('div', { className: 'empty' }, 'No agents yet.'));

  // teams
  specRoot.appendChild(sectionTitle('teams', spec.ai.teams.length));
  if (spec.ai.teams.length) spec.ai.teams.forEach(t => specRoot.appendChild(renderTeamCard(t)));
  else specRoot.appendChild(el('div', { className: 'empty' }, 'No teams yet.'));

  // workflows
  specRoot.appendChild(sectionTitle('workflows', spec.ai.workflows.length));
  if (spec.ai.workflows.length) spec.ai.workflows.forEach(w => specRoot.appendChild(renderWorkflowCard(w)));
  else specRoot.appendChild(el('div', { className: 'empty' }, 'No workflows yet.'));

  // knowledge
  const knowledgeCount =
    (spec.knowledge.types?.length || 0) + (spec.knowledge.principles?.sections?.length || 0);
  specRoot.appendChild(sectionTitle('knowledge', knowledgeCount));
  if (knowledgeCount) specRoot.appendChild(renderKnowledgeSection(spec.knowledge));
  else specRoot.appendChild(el('div', { className: 'empty' }, 'No knowledge types or principles yet.'));

  // parameters
  specRoot.appendChild(sectionTitle('parameters', spec.parameters.length));
  if (spec.parameters.length) spec.parameters.forEach(p => specRoot.appendChild(renderParameter(p)));
  else specRoot.appendChild(el('div', { className: 'empty' }, 'No parameters yet.'));

  // setup tasks (the operator's punch list after `agentorg render`)
  const setupSteps = spec.runtime?.setup || [];
  specRoot.appendChild(sectionTitle('setup tasks', setupSteps.length));
  if (setupSteps.length) setupSteps.forEach(s => specRoot.appendChild(renderSetupStep(s)));
  else specRoot.appendChild(el('div', { className: 'empty' }, 'No setup tasks yet.'));

  // env vars (required + optional)
  const required = spec.runtime?.env_vars?.required || [];
  const optional = spec.runtime?.env_vars?.optional || [];
  const envCount = required.length + optional.length;
  if (envCount) {
    specRoot.appendChild(sectionTitle('env vars', envCount));
    required.forEach(v => specRoot.appendChild(renderEnvVar(v, true)));
    optional.forEach(v => specRoot.appendChild(renderEnvVar(v, false)));
  }

  // custom tools
  if (custom_tools?.length) {
    specRoot.appendChild(sectionTitle('custom tools', custom_tools.length));
    custom_tools.forEach(t => specRoot.appendChild(renderCustomTool(t)));
  }
  // custom skills
  if (custom_skills?.length) {
    specRoot.appendChild(sectionTitle('custom skills', custom_skills.length));
    custom_skills.forEach(s => specRoot.appendChild(renderCustomSkill(s)));
  }
};

// ---------- API ----------

const fetchSpec = async () => {
  try {
    const r = await fetch('/api/spec');
    const data = await r.json();
    renderSpec(data);
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

const postRender = async () => {
  const r = await fetch('/api/render', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!r.ok) {
    let detail = null;
    try { detail = (await r.json()).detail; } catch { /* not JSON */ }
    if (detail?.blockers?.length) throw new Error('Not ready: ' + detail.blockers.join('; '));
    if (typeof detail === 'string') throw new Error(detail);
    throw new Error(`render ${r.status}`);
  }
  const slug = r.headers.get('X-AgentOrg-Slug') || lastReadiness.org_slug || 'org';
  return { blob: await r.blob(), filename: `${slug}.zip`, slug };
};

const triggerBlobDownload = (blob, filename) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 500);
};

// ---------- create-organization dialog ----------

const setDialogStatus = (kind, html) => {
  if (!kind) {
    createStatus.hidden = true;
    createStatus.className = 'dialog-status';
    createStatus.textContent = '';
    return;
  }
  createStatus.hidden = false;
  createStatus.className = `dialog-status ${kind}`;
  createStatus.innerHTML = html;
};

const openCreateDialog = () => {
  if (!lastReadiness.ready) return;
  createOrgName.textContent = lastOrgName || 'your org';
  createZipName.textContent = `${lastReadiness.org_slug || 'org'}.zip`;
  setDialogStatus(null);
  createConfirm.disabled = false;
  if (typeof createDialog.showModal === 'function') createDialog.showModal();
  else createDialog.setAttribute('open', '');
  setTimeout(() => createConfirm.focus(), 0);
};

const closeCreateDialog = () => {
  if (typeof createDialog.close === 'function') createDialog.close();
  else createDialog.removeAttribute('open');
};

const submitCreate = async (ev) => {
  ev.preventDefault();
  createConfirm.disabled = true;
  setDialogStatus('busy', 'Rendering project tree and packaging zip…');
  try {
    const { blob, filename, slug } = await postRender();
    triggerBlobDownload(blob, filename);
    const kb = Math.max(1, Math.round(blob.size / 1024));
    setDialogStatus('success', `Downloaded <code>${filename}</code> (${kb} KB). Extract it and open the README.`);
    appendMessage(
      'master',
      `Your org **${slug}** is ready — downloaded as \`${filename}\`. ` +
      `Extract the zip, then follow \`README.md\` inside for env vars, dependencies, and how to run it.`,
    );
    setTimeout(closeCreateDialog, 1400);
  } catch (e) {
    setDialogStatus('error', e.message);
    createConfirm.disabled = false;
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
      ? "\n\n_Your message is still in the input — press Enter to retry once Gemini comes back._"
      : '';
    appendMessage('master', `**Error:** ${e.message}${hint}`);
    chatInput.value = msg;  // restore so user can retry without retyping
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

const doReset = async () => {
  if (!confirm('Start over from scratch? The current draft will be discarded.')) return;
  try {
    await fetch('/api/reset', { method: 'POST' });
    showEmptyHero();
    await fetchSpec();
    chatInput.focus();
  } catch (e) {
    appendMessage('master', `**Error resetting:** ${e.message}`);
  }
};

resetBtn.addEventListener('click', doReset);
createBtn.addEventListener('click', openCreateDialog);
createCancel.addEventListener('click', closeCreateDialog);
createForm.addEventListener('submit', submitCreate);

showEmptyHero();
fetchSpec();
chatInput.focus();
