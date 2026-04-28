const state = {
  uiState: null,
  projects: [],
  requirements: [],
  requirementTree: [],
  changeRequests: [],
  runs: [],
  selectedRequirementId: null,
  selectedCrId: null,
  selectedRunId: null,
  busy: new Set(),
  runsAllLoaded: false,
  defaultRunsLimit: 50,
};

const FINAL_CR_STATUSES = new Set(['applied']);
const BUSY_CR_STATUSES = new Set(['analyzing', 'running', 'selecting_target']);

const api = {
  async get(path) {
    const response = await fetch(path);
    return handleResponse(response);
  },
  async post(path, body = {}) {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return handleResponse(response);
  },
  async put(path, body = {}) {
    const response = await fetch(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return handleResponse(response);
  },
  async delete(path) {
    const response = await fetch(path, { method: 'DELETE' });
    return handleResponse(response);
  },
};

async function handleResponse(response) {
  const text = await response.text();
  let payload = null;
  if (text) {
    try { payload = JSON.parse(text); } catch (_) { payload = text; }
  }
  if (!response.ok) {
    const message = payload?.error?.message || payload?.detail || text || `HTTP ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

function $(id) { return document.getElementById(id); }
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
}
function jsonBlock(value) { return `<pre class="json-block">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`; }
function codeBlock(value) { return `<pre class="code-block">${escapeHtml(value || '')}</pre>`; }
function shortText(value, len = 130) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  return text.length > len ? `${text.slice(0, len)}…` : text;
}
function badge(text, kind = '') { return `<span class="badge ${kind}">${escapeHtml(text || '—')}</span>`; }
function statusBadge(value) {
  const text = String(value || '—');
  const low = text.toLowerCase();
  if (low.includes('верифицировано') && !low.includes('не ')) return badge(text, 'ok');
  if (low.includes('ok') || low.includes('ready') || low.includes('passed') || low === 'applied') return badge(text, 'ok');
  if (low.includes('fail') || low.includes('error') || low.includes('ошибка')) return badge(text, 'err');
  if (low.includes('running') || low.includes('analyzing') || low.includes('selecting')) return badge('выполняется', 'info');
  if (low.includes('не верифицировано')) return badge(text, 'warn');
  return badge(text);
}
function isFinalCr(cr) { return Boolean(cr?.applied_at || cr?.applied_run_id || FINAL_CR_STATUSES.has(String(cr?.status || '').toLowerCase())); }
function isBusyCr(cr) { return BUSY_CR_STATUSES.has(String(cr?.status || '').toLowerCase()) || state.busy.has(cr?.cr_id); }
function canWorkWithCr(cr) { return Boolean(cr && !isFinalCr(cr) && !isBusyCr(cr)); }
function canDeleteCr(cr) { return cr && !isFinalCr(cr) && !isBusyCr(cr); }
function canApplyCr(cr) {
  return Boolean(cr?.last_run_id && cr?.last_workspace_id && !isFinalCr(cr) && String(cr?.status || '') === 'ready_for_merge_review');
}

function linesFromTextarea(value) {
  return String(value || '').split('\n').map(v => v.trim()).filter(Boolean);
}
function linesToTextarea(values) {
  return (values || []).join('\n');
}
function findCrForRun(runId) {
  return state.changeRequests.find(cr => (cr.run_ids || []).includes(runId) || cr.last_run_id === runId) || null;
}
function crHasPipelineState(cr) {
  return Boolean(cr?.session_id || cr?.recommended_target || cr?.selected_target || cr?.last_run_id || (cr?.run_ids || []).length);
}

async function init() {
  bindNavigation();
  bindToolbar();
  await loadAll();
}

function bindNavigation() {
  document.querySelectorAll('.nav-item').forEach(button => {
    button.addEventListener('click', () => setActiveView(button.dataset.view));
  });
}

function setActiveView(viewId) {
  document.querySelectorAll('.nav-item').forEach(button => button.classList.toggle('active', button.dataset.view === viewId));
  document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.id === viewId));
}

function bindToolbar() {
  $('select-project-btn').addEventListener('click', selectProjectFromDropdown);
  $('refresh-projects-btn').addEventListener('click', async () => { await loadProjects(); renderProjectPanel(); });
  $('show-register-project-btn').addEventListener('click', toggleProjectRegisterForm);
  $('register-project-form').addEventListener('submit', registerProject);
  $('set-requirements-path-btn').addEventListener('click', setRequirementsPath);
  $('reload-requirements-btn').addEventListener('click', async () => { await loadRequirements(); renderRequirements(); });
  $('refresh-runs-btn').addEventListener('click', async () => { await loadRuns({ all: state.runsAllLoaded }); renderRuns(); });
  $('show-all-runs-btn').addEventListener('click', async event => {
    await withBusyButton(event.currentTarget, 'Загрузка...', async () => {
      await loadRuns({ all: true });
      renderRuns();
    });
  });
}

async function loadAll() {
  try {
    setApiStatus('API');
    const [uiState, projects, changeRequests, runs] = await Promise.all([
      api.get('/api/ui-state'),
      api.get('/api/projects'),
      api.get('/api/change-requests'),
      api.get('/api/runs?limit=50'),
    ]);
    state.uiState = uiState;
    state.projects = projects.items || [];
    state.changeRequests = changeRequests.items || [];
    state.runs = runs.items || [];
    state.runsAllLoaded = false;
    state.selectedRequirementId = uiState.selected_requirement_ids?.[0] || null;
    state.selectedCrId = uiState.selected_change_request_id || null;
    await loadRequirements();
    renderAll();
    setApiStatus('API');
  } catch (error) {
    setApiStatus('Ошибка', true);
    alert(error.message);
  }
}

async function loadProjects() {
  const result = await api.get('/api/projects');
  state.projects = result.items || [];
}
async function loadRequirements() {
  const [list, tree] = await Promise.all([api.get('/api/requirements'), api.get('/api/requirements/tree')]);
  state.requirements = list.items || [];
  state.requirementTree = tree.items || [];
}
async function loadChangeRequests() {
  const result = await api.get('/api/change-requests');
  state.changeRequests = result.items || [];
}
async function loadRuns({ all = false } = {}) {
  const result = await api.get(all ? '/api/runs?all=true' : `/api/runs?limit=${state.defaultRunsLimit}`);
  state.runs = result.items || [];
  state.runsAllLoaded = all;
}

function renderAll() {
  renderProjectPanel();
  renderRequirements();
  renderCrList();
  renderSelectedCr();
  renderRuns();
}

function setApiStatus(text, error = false) {
  const el = $('api-status');
  el.textContent = text;
  el.classList.toggle('error', error);
}

function renderProjectPanel() {
  const select = $('project-select');
  const selectedId = state.uiState?.selected_project_id || '';
  select.innerHTML = `<option value="">Не выбран</option>` + state.projects.map(project => {
    const selected = project.project_id === selectedId ? 'selected' : '';
    return `<option value="${escapeHtml(project.project_id)}" ${selected}>${escapeHtml(project.project_name || project.project_id)}</option>`;
  }).join('');
  const project = state.projects.find(item => item.project_id === selectedId);
  $('project-path').textContent = project ? `${project.project_name || project.project_id} · ${project.project_root}` : 'Проект не выбран';
}
function toggleProjectRegisterForm() { $('register-project-panel').classList.toggle('hidden'); }

async function registerProject(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  const data = new FormData(form);
  const projectRoot = String(data.get('project_root') || '').trim();
  if (!projectRoot) { alert('Укажите путь к проекту.'); return; }
  const payload = {
    project_root: projectRoot,
    project_name: String(data.get('project_name') || '').trim() || null,
    languages: String(data.get('languages') || 'python').split(',').map(v => v.trim()).filter(Boolean),
    verification_commands: String(data.get('verification_commands') || '').split('\n').map(v => v.trim()).filter(Boolean),
    index_excludes: String(data.get('index_excludes') || '').split('\n').map(v => v.trim()).filter(Boolean),
    reference_library_paths: String(data.get('reference_library_paths') || '').split('\n').map(v => v.trim()).filter(Boolean),
  };
  await withBusyButton(button, 'Регистрация...', async () => {
    const result = await api.post('/api/projects/register', payload);
    const project = result.project || result;
    await loadProjects();
    if (project.project_id) {
      state.uiState = await api.post('/api/ui-state/select-project', { project_id: project.project_id });
    }
    renderProjectPanel();
    $('register-project-panel').classList.add('hidden');
    form.reset();
  });
}

async function selectProjectFromDropdown() {
  const projectId = $('project-select').value;
  if (!projectId) return;
  state.uiState = await api.post('/api/ui-state/select-project', { project_id: projectId });
  renderProjectPanel();
}

async function setRequirementsPath() {
  const path = $('requirements-path-input').value.trim();
  if (!path) return;
  try {
    state.uiState = await api.post('/api/ui-state/requirements-file', { path });
    state.selectedRequirementId = null;
    await loadRequirements();
    renderRequirements();
  } catch (error) { alert(error.message); }
}

function renderRequirements() {
  $('requirements-count').textContent = String(state.requirements.length);
  $('requirements-path-input').value = state.uiState?.requirements_file_path || '';
  $('requirements-tree').innerHTML = renderTreeNodes(state.requirementTree, 0);
  $('requirements-tree').querySelectorAll('[data-requirement-id]').forEach(el => {
    el.addEventListener('click', () => selectRequirement(el.dataset.requirementId));
  });
  if (state.selectedRequirementId && state.requirements.some(item => item.id === state.selectedRequirementId)) {
    renderRequirementDetail(state.requirements.find(item => item.id === state.selectedRequirementId));
  } else {
    $('requirement-detail').innerHTML = '<div class="empty-state">Выберите требование слева.</div>';
  }
}

function renderTreeNodes(nodes, level) {
  return (nodes || []).map(node => {
    const item = node.item;
    const active = item.id === state.selectedRequirementId ? 'active' : '';
    const indent = `tree-indent-${Math.min(level, 5)}`;
    return `
      <div class="tree-item ${active} ${indent}" data-requirement-id="${escapeHtml(item.id)}">
        <div class="tree-line">
          ${badge(item.type || 'REQ', 'blue')}
          <span class="item-title">${escapeHtml(item.id)}</span>
          ${statusBadge(item.verification_status || item.status)}
        </div>
        <div class="item-meta">${escapeHtml(shortText(item.description || item.title, 115))}</div>
      </div>
      ${renderTreeNodes(node.children || [], level + 1)}
    `;
  }).join('');
}

async function selectRequirement(requirementId) {
  state.selectedRequirementId = requirementId;
  try { state.uiState = await api.put('/api/ui-state', { selected_requirement_ids: [requirementId] }); }
  catch (error) { alert(error.message); }
  renderRequirements();
}

function renderRequirementDetail(item) {
  const related = state.changeRequests.filter(cr => (cr.requirement_ids || []).includes(item.id));
  $('requirement-detail').innerHTML = `
    <div class="detail-scroll">
      <div class="card">
        <h3 class="card-title">Выбранное требование</h3>
        <div class="kv-grid">
          <div class="key">ID</div><div>${escapeHtml(item.id)}</div>
          <div class="key">Тип</div><div>${badge(item.type || '—', 'blue')}</div>
          <div class="key">Статус</div><div>${escapeHtml(item.status || '—')}</div>
          <div class="key">Проверка</div><div>${statusBadge(item.verification_status || '—')}</div>
          <div class="key">Родитель</div><div>${escapeHtml(item.parent_id || '—')}</div>
          <div class="key">Дата</div><div>${escapeHtml(item.created_at || '—')}</div>
        </div>
        <div class="description">${escapeHtml(item.description)}</div>
        ${item.note ? `<div class="message"><b>Примечание:</b> ${escapeHtml(item.note)}</div>` : ''}
      </div>
      <div class="card">
        <h3 class="card-title">Создать запрос на изменение</h3>
        ${renderCreateCrForm()}
      </div>
      <div class="card">
        <h3 class="card-title">Связанные запросы</h3>
        ${renderRelatedCrs(related)}
      </div>
    </div>
  `;
  bindCreateCrForm(item);
  $('requirement-detail').querySelectorAll('[data-open-cr]').forEach(el => el.addEventListener('click', () => openCr(el.dataset.openCr)));
}

function renderCreateCrForm() {
  return `
    <form id="create-cr-form" class="form-grid">
      <div class="form-row"><label>Код запроса</label><input name="code" placeholder="Заполнится автоматически, если оставить пустым"></div>
      <div class="form-row"><label>Название</label><input name="title" required placeholder="Введите название запроса вручную"></div>
      <div class="form-row"><label>Описание</label><textarea name="description" rows="4" required placeholder="Опишите изменение, которое нужно выполнить"></textarea></div>
      <div class="form-row"><label>Ограничения</label><textarea name="constraints" rows="2" placeholder="По одному ограничению на строку"></textarea></div>
      <div class="form-row"><label>Операция</label><select name="requested_operation"><option value="replace_symbol">заменить существующий код</option><option value="insert_after_symbol">добавить после существующего кода</option></select></div>
      <div class="action-row"><button class="btn" type="submit">Создать запрос</button></div>
    </form>
  `;
}

function bindCreateCrForm(requirement) {
  const form = $('create-cr-form');
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const projectId = state.uiState?.selected_project_id;
    if (!projectId) { alert('Сначала выберите проект на верхней панели.'); return; }
    const data = new FormData(form);
    const title = String(data.get('title') || '').trim();
    const description = String(data.get('description') || '').trim();
    if (!title || !description) {
      alert('Заполните поля «Название» и «Описание» вручную.');
      return;
    }
    const payload = {
      project_id: projectId,
      requirement_id: requirement.id,
      requirement_ids: [requirement.id],
      code: String(data.get('code') || '').trim() || null,
      title,
      description,
      constraints: String(data.get('constraints') || '').split('\n').map(v => v.trim()).filter(Boolean),
      requested_operation: data.get('requested_operation'),
    };
    const button = form.querySelector('button[type="submit"]');
    await withBusyButton(button, 'Создание...', async () => {
      const created = await api.post('/api/change-requests', payload);
      state.selectedCrId = created.cr_id;
      state.uiState = await api.put('/api/ui-state', { selected_change_request_id: created.cr_id });
      await loadChangeRequests();
      renderRequirementDetail(requirement);
      renderCrList();
      openCr(created.cr_id);
    });
  });
}

function renderRelatedCrs(items) {
  if (!items.length) return '<div class="empty-state">Для выбранного требования запросы еще не созданы.</div>';
  return items.map(cr => `
    <div class="list-item" data-open-cr="${escapeHtml(cr.cr_id)}">
      <div class="item-title">${escapeHtml(cr.code || cr.cr_id)} · ${escapeHtml(cr.title)}</div>
      <div class="item-meta">${statusBadge(cr.status)} ${escapeHtml(cr.cr_id)}</div>
    </div>
  `).join('');
}

function openCr(crId) {
  state.selectedCrId = crId;
  setActiveView('requests-view');
  renderCrList();
  renderSelectedCr();
}

function renderCrList() {
  $('cr-count').textContent = String(state.changeRequests.length);
  const root = $('cr-list');
  if (!state.changeRequests.length) {
    root.innerHTML = '<div class="empty-state">Запросы пока не созданы.</div>';
    return;
  }
  root.innerHTML = state.changeRequests.map(cr => `
    <div class="list-item ${cr.cr_id === state.selectedCrId ? 'active' : ''}" data-cr-id="${escapeHtml(cr.cr_id)}">
      <div class="item-title">${escapeHtml(cr.code || cr.cr_id)} · ${escapeHtml(cr.title)}</div>
      <div class="item-meta">${statusBadge(cr.status)} ${escapeHtml((cr.requirement_ids || []).join(', ') || 'без требования')}</div>
    </div>
  `).join('');
  root.querySelectorAll('[data-cr-id]').forEach(el => el.addEventListener('click', async () => {
    state.selectedCrId = el.dataset.crId;
    try { state.uiState = await api.put('/api/ui-state', { selected_change_request_id: state.selectedCrId }); } catch (_) {}
    renderCrList();
    renderSelectedCr();
  }));
}

function renderSelectedCr() {
  const cr = state.changeRequests.find(item => item.cr_id === state.selectedCrId);
  if (!cr) {
    $('cr-detail').innerHTML = '<div class="empty-state">Выберите запрос или создайте его из требования.</div>';
    return;
  }
  const candidates = cr.raw?.last_analyze_result?.candidates || [];
  $('cr-detail').innerHTML = `
    <div class="detail-scroll">
      <div class="card">
        <h3 class="card-title">Запрос на изменение</h3>
        <div class="kv-grid">
          <div class="key">Код</div><div>${escapeHtml(cr.code || '—')}</div>
          <div class="key">Технический ID</div><div>${escapeHtml(cr.cr_id)}</div>
          <div class="key">Статус</div><div>${statusBadge(cr.status)}</div>
          <div class="key">Проект</div><div>${escapeHtml(cr.project_id)}</div>
          <div class="key">Требования</div><div>${escapeHtml((cr.requirement_ids || []).join(', ') || '—')}</div>
          <div class="key">Операция</div><div>${escapeHtml(operationLabel(cr.requested_operation))}</div>
          <div class="key">Сессия анализа</div><div>${escapeHtml(cr.session_id || '—')}</div>
          <div class="key">Рекомендованное место</div><div>${escapeHtml(cr.recommended_target || '—')}</div>
          <div class="key">Выбранное место</div><div>${escapeHtml(cr.selected_target || '—')}</div>
          <div class="key">Последний запуск</div><div>${escapeHtml(cr.last_run_id || '—')}</div>
        </div>
      </div>

      <div class="card">
        <h3 class="card-title">Поля запроса</h3>
        ${renderCrEditForm(cr)}
      </div>

      <div class="card">
        <h3 class="card-title">Связанные требования</h3>
        ${renderCrRequirements(cr)}
      </div>
      <div class="card">
        <h3 class="card-title">Запуски по запросу</h3>
        ${renderCrRuns(cr)}
      </div>
      <div class="card">
        <h3 class="card-title">Действия</h3>
        <div class="action-row">
          <button class="btn" id="analyze-cr-btn" ${!canWorkWithCr(cr) ? 'disabled' : ''}>Выполнить анализ</button>
          <button class="btn" id="run-cr-btn" ${!canWorkWithCr(cr) ? 'disabled' : ''}>Запустить обработку</button>
          ${cr.last_run_id ? '<button class="btn" id="open-run-btn">Открыть последний результат</button>' : ''}
          ${canApplyCr(cr) ? '<button class="btn" id="apply-cr-btn">Применить последний результат</button>' : ''}
          ${canDeleteCr(cr) ? '<button class="btn danger" id="delete-cr-btn">Удалить запрос</button>' : ''}
        </div>
      </div>
      <div class="tabs">
        <button class="tab-btn active" data-tab="cr-candidates">Место изменения</button>
        <button class="tab-btn" data-tab="cr-json">JSON</button>
      </div>
      <div id="cr-candidates" class="tab-panel active">${renderCandidates(candidates, cr)}</div>
      <div id="cr-json" class="tab-panel">${jsonBlock(cr)}</div>
    </div>
  `;
  bindTabs($('cr-detail'));
  bindCrEditForm(cr);
  $('analyze-cr-btn').addEventListener('click', event => analyzeCr(cr.cr_id, event.currentTarget));
  $('run-cr-btn').addEventListener('click', event => runCr(cr.cr_id, event.currentTarget));
  const openRun = $('open-run-btn');
  if (openRun) openRun.addEventListener('click', () => openRunView(cr.last_run_id));
  const applyBtn = $('apply-cr-btn');
  if (applyBtn) applyBtn.addEventListener('click', event => applyLastRun(cr.cr_id, event.currentTarget));
  const deleteBtn = $('delete-cr-btn');
  if (deleteBtn) deleteBtn.addEventListener('click', event => deleteCr(cr.cr_id, event.currentTarget));
  $('cr-detail').querySelectorAll('[data-select-target]').forEach(button => button.addEventListener('click', event => selectTarget(cr.cr_id, button.dataset.selectTarget, event.currentTarget)));
  $('cr-detail').querySelectorAll('[data-open-run]').forEach(el => el.addEventListener('click', () => openRunView(el.dataset.openRun)));
  const manualBtn = $('manual-target-btn');
  if (manualBtn) manualBtn.addEventListener('click', event => selectManualTarget(cr, event.currentTarget));
}

function operationLabel(value) {
  if (value === 'insert_after_symbol') return 'добавить после существующего кода';
  if (value === 'replace_symbol') return 'заменить существующий код';
  return value || '—';
}

function renderCrEditForm(cr) {
  const disabled = isFinalCr(cr) || isBusyCr(cr);
  return `
    <form id="edit-cr-form" class="form-grid">
      <div class="form-row"><label>Код запроса</label><input name="code" value="${escapeHtml(cr.code || '')}" ${disabled ? 'disabled' : ''}></div>
      <div class="form-row"><label>Название</label><input name="title" value="${escapeHtml(cr.title || '')}" required ${disabled ? 'disabled' : ''}></div>
      <div class="form-row"><label>Описание</label><textarea name="description" rows="4" required ${disabled ? 'disabled' : ''}>${escapeHtml(cr.description || '')}</textarea></div>
      <div class="form-row"><label>Ограничения</label><textarea name="constraints" rows="3" ${disabled ? 'disabled' : ''}>${escapeHtml(linesToTextarea(cr.constraints || []))}</textarea></div>
      <div class="form-row"><label>Операция</label><select name="requested_operation" ${disabled ? 'disabled' : ''}>
        <option value="replace_symbol" ${cr.requested_operation === 'replace_symbol' ? 'selected' : ''}>заменить существующий код</option>
        <option value="insert_after_symbol" ${cr.requested_operation === 'insert_after_symbol' ? 'selected' : ''}>добавить после существующего кода</option>
      </select></div>
      <div class="form-row"><label>Примечания</label><textarea name="notes" rows="2" ${disabled ? 'disabled' : ''}>${escapeHtml(linesToTextarea(cr.notes || []))}</textarea></div>
      <div class="action-row">
        <button class="btn" type="submit" ${disabled ? 'disabled' : ''}>Сохранить изменения</button>
        ${crHasPipelineState(cr) && !disabled ? '<span class="message">При сохранении анализ, выбранное место и список запусков будут сброшены.</span>' : ''}
        ${isFinalCr(cr) ? '<span class="message">Запрос уже применен к основному проекту и не может быть изменен.</span>' : ''}
      </div>
    </form>
  `;
}

function bindCrEditForm(cr) {
  const form = $('edit-cr-form');
  if (!form) return;
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const data = new FormData(form);
    const title = String(data.get('title') || '').trim();
    const description = String(data.get('description') || '').trim();
    if (!title || !description) {
      alert('Заполните поля «Название» и «Описание».');
      return;
    }
    if (crHasPipelineState(cr) && !confirm('Сохранение изменит исходные данные запроса и сбросит результаты анализа, выбранное место изменения и связанные запуски. Продолжить?')) {
      return;
    }
    const payload = {
      code: String(data.get('code') || '').trim() || null,
      title,
      description,
      constraints: linesFromTextarea(data.get('constraints')),
      notes: linesFromTextarea(data.get('notes')),
      requested_operation: data.get('requested_operation'),
    };
    const button = form.querySelector('button[type="submit"]');
    await withBusyButton(button, 'Сохранение...', async () => {
      const updated = await api.put(`/api/change-requests/${encodeURIComponent(cr.cr_id)}`, payload);
      state.selectedCrId = updated.cr_id;
      await loadChangeRequests();
      renderCrList();
      renderSelectedCr();
      if (state.selectedRequirementId) {
        const req = state.requirements.find(item => item.id === state.selectedRequirementId);
        if (req) renderRequirementDetail(req);
      }
    });
  });
}

function renderCrRequirements(cr) {
  const snapshots = cr.requirements_snapshot || [];
  if (!snapshots.length) return '<div class="empty-state">Связанные требования не указаны.</div>';
  return snapshots.map(req => `
    <div class="list-item">
      <div class="item-title">${escapeHtml(req.id)} ${req.missing ? statusBadge('недоступно') : ''}</div>
      <div class="item-meta">${escapeHtml(req.type || '')} ${escapeHtml(shortText(req.description || req.title, 160))}</div>
    </div>
  `).join('');
}

function renderCrRuns(cr) {
  const ids = cr.run_ids || [];
  if (!ids.length) return '<div class="empty-state">Запусков по этому запросу пока нет.</div>';
  return `<table class="table"><thead><tr><th>Запуск</th><th>Статус</th><th>Проверки</th><th>Применение</th><th></th></tr></thead><tbody>${ids.map(runId => {
    const run = state.runs.find(item => item.run_id === runId) || { run_id: runId, status: '—' };
    const latest = cr.last_run_id === runId;
    return `<tr>
      <td>${escapeHtml(runId)} ${latest ? badge('последний', 'info') : ''}</td>
      <td>${statusBadge(run.status)}</td>
      <td>${run.verification_passed === true ? statusBadge('успешно', 'ok') : run.verification_passed === false ? statusBadge('не пройдены', 'warn') : '—'}</td>
      <td>${run.merge_ready === true ? statusBadge('готов', 'ok') : run.merge_ready === false ? statusBadge('нет', 'warn') : '—'}</td>
      <td><button class="btn small" data-open-run="${escapeHtml(runId)}">Открыть</button></td>
    </tr>`;
  }).join('')}</tbody></table>`;
}

function renderCandidates(candidates, cr) {
  const manualBlock = renderManualTargetBlock(cr);
  if (!candidates.length) {
    return `${manualBlock}<div class="empty-state">Кандидаты появятся после выполнения анализа. Если анализ уже выполнен, место изменения можно указать вручную.</div>`;
  }
  return `${manualBlock}<table class="table"><thead><tr><th>Место изменения</th><th>Оценка</th><th>Причины</th><th></th></tr></thead><tbody>${candidates.map(candidate => `
    <tr>
      <td><b>${escapeHtml(candidate.name || '')}</b><br><span class="item-meta">${escapeHtml(candidate.qualname)}</span><br><span class="item-meta">${escapeHtml(candidate.file_path)}</span></td>
      <td>${escapeHtml(candidate.score)}<br>${escapeHtml(candidate.relevance_category || '')}</td>
      <td>${(candidate.reasons || []).slice(0, 4).map(escapeHtml).join('<br>')}</td>
      <td><button class="btn small ${cr.selected_target === candidate.qualname ? 'selected' : ''}" data-select-target="${escapeHtml(candidate.qualname)}" ${!canWorkWithCr(cr) ? 'disabled' : ''}>Выбрать</button></td>
    </tr>
  `).join('')}</tbody></table>`;
}

function renderManualTargetBlock(cr) {
  const disabled = !cr.session_id || isBusyCr(cr) || isFinalCr(cr);
  const hint = cr.session_id
    ? 'Укажите полное имя символа, если нужного варианта нет в списке.'
    : 'Ручной выбор будет доступен после анализа запроса.';
  return `
    <div class="manual-target-panel">
      <div class="form-row"><label>Место изменения</label><input id="manual-target-input" value="${escapeHtml(cr.selected_target || '')}" placeholder="package.module.Class.method" ${disabled ? 'disabled' : ''}></div>
      <div class="action-row">
        <button class="btn small" id="manual-target-btn" ${disabled ? 'disabled' : ''}>Выбрать вручную</button>
        <span class="message">${escapeHtml(hint)}</span>
      </div>
    </div>
  `;
}

async function selectManualTarget(cr, button) {
  const input = $('manual-target-input');
  const qualname = String(input?.value || '').trim();
  if (!qualname) { alert('Укажите полное имя места изменения.'); return; }
  await selectTarget(cr.cr_id, qualname, button);
}

async function refreshCrAfterAction({ reloadRuns = false } = {}) {
  if (reloadRuns) {
    await Promise.all([loadChangeRequests(), loadRuns()]);
  } else {
    await loadChangeRequests();
  }
  renderCrList();
  renderSelectedCr();
  if (reloadRuns) renderRuns();
}

async function analyzeCr(crId, button) {
  if (state.busy.has(crId)) return;
  state.busy.add(crId);
  try {
    await withBusyButton(button, 'Анализ...', async () => {
      await api.post(`/api/change-requests/${encodeURIComponent(crId)}/analyze`, {});
    });
  } finally {
    state.busy.delete(crId);
    await refreshCrAfterAction();
  }
}
async function selectTarget(crId, qualname, button) {
  if (state.busy.has(crId)) return;
  state.busy.add(crId);
  try {
    await withBusyButton(button, 'Выбор...', async () => {
      await api.post(`/api/change-requests/${encodeURIComponent(crId)}/select-target`, { selected_qualname: qualname });
    });
  } finally {
    state.busy.delete(crId);
    await refreshCrAfterAction();
  }
}
async function runCr(crId, button) {
  if (state.busy.has(crId)) return;
  state.busy.add(crId);
  try {
    await withBusyButton(button, 'Выполняется...', async () => {
      await api.post(`/api/change-requests/${encodeURIComponent(crId)}/run`, {});
    });
  } finally {
    state.busy.delete(crId);
    await refreshCrAfterAction({ reloadRuns: true });
  }
}
async function applyLastRun(crId, button) {
  if (!confirm('Применить последний результат в основной проект?')) return;
  await withBusyButton(button, 'Применение...', async () => {
    await api.post(`/api/change-requests/${encodeURIComponent(crId)}/apply-last-run`, {});
    await Promise.all([loadChangeRequests(), loadRuns()]);
    renderCrList();
    renderSelectedCr();
    renderRuns();
  });
}
async function deleteCr(crId, button) {
  if (!confirm('Удалить запрос на изменение?')) return;
  await withBusyButton(button, 'Удаление...', async () => {
    await api.delete(`/api/change-requests/${encodeURIComponent(crId)}`);
    state.selectedCrId = null;
    await api.put('/api/ui-state', { selected_change_request_id: null }).catch(() => null);
    await loadChangeRequests();
    renderCrList();
    renderSelectedCr();
    if (state.selectedRequirementId) {
      const req = state.requirements.find(item => item.id === state.selectedRequirementId);
      if (req) renderRequirementDetail(req);
    }
  });
}

function renderRuns() {
  const root = $('run-list');
  $('runs-count').textContent = state.runsAllLoaded ? String(state.runs.length) : `${state.runs.length}/${state.defaultRunsLimit}`;
  const showAllBtn = $('show-all-runs-btn');
  if (showAllBtn) showAllBtn.disabled = state.runsAllLoaded;
  if (!state.runs.length) { root.innerHTML = '<div class="empty-state">Запусков пока нет.</div>'; return; }
  const limitNote = state.runsAllLoaded ? '' : '<div class="message compact-message">Показаны последние запуски. Старый запуск можно открыть из связанного CR или загрузить весь список.</div>';
  root.innerHTML = limitNote + state.runs.map(run => `
    <div class="list-item ${run.run_id === state.selectedRunId ? 'active' : ''}" data-run-id="${escapeHtml(run.run_id)}">
      <div class="item-title">${escapeHtml(run.run_id)}</div>
      <div class="item-meta">${statusBadge(run.status)} ${escapeHtml(run.selected_target || '')}</div>
    </div>
  `).join('');
  root.querySelectorAll('[data-run-id]').forEach(el => el.addEventListener('click', () => openRunView(el.dataset.runId)));
}

async function openRunView(runId) {
  if (!runId) return;
  state.selectedRunId = runId;
  await ensureRunInList(runId);
  setActiveView('runs-view');
  renderRuns();
  await renderRunDetail(runId);
}

async function ensureRunInList(runId) {
  if (state.runs.some(run => run.run_id === runId)) return;
  try {
    const summary = await api.get(`/api/runs/${encodeURIComponent(runId)}/summary`);
    state.runs.unshift({
      run_id: runId,
      run_label: summary.run_label,
      status: summary.status,
      selected_target: summary.selected_target,
      changed_files: summary.changed_files || [],
      verification_passed: summary.verification_passed,
      merge_ready: summary.merge_ready,
      created_at: summary.run_label || runId,
    });
  } catch (_) {
    state.runs.unshift({ run_id: runId, status: 'недоступен' });
  }
}

async function renderRunDetail(runId) {
  const root = $('run-detail');
  root.innerHTML = '<div class="empty-state">Загрузка результата...</div>';
  try {
    const [summary, steps, checks, diff, code, test] = await Promise.all([
      api.get(`/api/runs/${encodeURIComponent(runId)}/summary`),
      api.get(`/api/runs/${encodeURIComponent(runId)}/steps`),
      api.get(`/api/runs/${encodeURIComponent(runId)}/checks`),
      api.get(`/api/runs/${encodeURIComponent(runId)}/diff`),
      api.get(`/api/runs/${encodeURIComponent(runId)}/code`),
      api.get(`/api/runs/${encodeURIComponent(runId)}/test`),
    ]);
    root.innerHTML = `
      <div class="detail-scroll">
        ${renderRunContext(runId)}
        <div class="card"><h3 class="card-title">Результат запуска</h3>${renderRunSummary(summary)}</div>
        <div class="tabs">
          <button class="tab-btn active" data-tab="run-steps">Шаги</button>
          <button class="tab-btn" data-tab="run-checks">Проверки</button>
          <button class="tab-btn" data-tab="run-diff">Diff</button>
          <button class="tab-btn" data-tab="run-code">Код</button>
          <button class="tab-btn" data-tab="run-test">Тест</button>
        </div>
        <div id="run-steps" class="tab-panel active">${renderSteps(steps)}</div>
        <div id="run-checks" class="tab-panel">${renderChecks(checks)}</div>
        <div id="run-diff" class="tab-panel">${codeBlock(diff.unified_diff || '')}</div>
        <div id="run-code" class="tab-panel">${renderArtifact(code, 'code')}</div>
        <div id="run-test" class="tab-panel">${renderArtifact(test, 'test')}</div>
      </div>
    `;
    bindTabs(root);
  } catch (error) {
    root.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  }
}

function renderRunContext(runId) {
  const cr = findCrForRun(runId);
  if (!cr) {
    return '<div class="card"><h3 class="card-title">Связанный запрос</h3><div class="empty-state">Связанный запрос не найден. Возможно, запуск создан вне codeui или связь была сброшена после редактирования CR.</div></div>';
  }
  return `
    <div class="card">
      <h3 class="card-title">Связанный запрос</h3>
      <div class="kv-grid">
        <div class="key">Код запроса</div><div>${escapeHtml(cr.code || '—')}</div>
        <div class="key">Название</div><div>${escapeHtml(cr.title || '—')}</div>
        <div class="key">Описание</div><div>${escapeHtml(cr.description || '—')}</div>
        <div class="key">Ограничения</div><div>${escapeHtml((cr.constraints || []).join('; ') || '—')}</div>
        <div class="key">Статус запроса</div><div>${statusBadge(cr.status)}</div>
        <div class="key">Последний запуск</div><div>${escapeHtml(cr.last_run_id || '—')} ${cr.last_run_id === runId ? badge('последний', 'info') : ''}</div>
      </div>
      <div class="subsection-title">Связанные требования</div>
      ${renderCrRequirements(cr)}
    </div>
  `;
}

function renderRunSummary(summary) {
  return `<div class="kv-grid">
    <div class="key">Статус</div><div>${statusBadge(summary.status)}</div>
    <div class="key">Место изменения</div><div>${escapeHtml(summary.selected_target || '—')}</div>
    <div class="key">Проверки</div><div>${summary.verification_passed ? statusBadge('успешно', 'ok') : statusBadge('не пройдены', 'warn')}</div>
    <div class="key">Готов к применению</div><div>${summary.merge_ready ? statusBadge('да', 'ok') : statusBadge('нет', 'warn')}</div>
    <div class="key">Файлы</div><div>${escapeHtml((summary.changed_files || []).join(', ') || '—')}</div>
  </div>`;
}
function renderSteps(steps) {
  return `<table class="table"><thead><tr><th>Шаг</th><th>Статус</th><th>Время</th><th>Токены</th><th>Описание</th></tr></thead><tbody>${(steps || []).map(step => `
    <tr><td>${escapeHtml(step.step_name)}</td><td>${statusBadge(step.status)}</td><td>${escapeHtml(step.duration_ms ?? '—')} мс</td><td>${escapeHtml(step.usage?.total_tokens ?? '—')}</td><td>${escapeHtml(step.summary || '')}</td></tr>
  `).join('')}</tbody></table>`;
}
function renderChecks(checks) {
  return `<table class="table checks-table"><thead><tr><th>Проверка</th><th>Результат</th><th>Уровень</th><th>Проблемы</th></tr></thead><tbody>${(checks || []).map(check => `
    <tr>
      <td>${escapeHtml(check.name)}</td>
      <td>${check.ok ? statusBadge('ok', 'ok') : statusBadge('ошибка', 'err')}</td>
      <td>${escapeHtml(check.severity || '')}</td>
      <td>${renderIssues(check.issues, check.details)}</td>
    </tr>
  `).join('')}</tbody></table>`;
}

function renderIssues(issues, details) {
  const normalized = Array.isArray(issues) ? issues : [];
  const detailObj = details && typeof details === 'object' && !Array.isArray(details) ? details : null;
  if (!normalized.length && !detailObj) return '<span class="muted">—</span>';

  const issueHtml = normalized.length
    ? `<div class="issue-list">${normalized.map(renderIssue).join('')}</div>`
    : '';

  const detailsHtml = detailObj
    ? `<details class="compact-details"><summary>Детали проверки</summary>${jsonBlock(detailObj)}</details>`
    : '';

  return `${issueHtml}${detailsHtml}`;
}

function renderIssue(issue) {
  if (issue == null) return '<div class="issue-item">—</div>';
  if (typeof issue !== 'object' || Array.isArray(issue)) {
    return `<div class="issue-item">${escapeHtml(String(issue))}</div>`;
  }

  const code = issue.code ? `<span class="issue-code">${escapeHtml(issue.code)}</span>` : '';
  const severity = issue.severity ? `<span class="issue-severity">${escapeHtml(issue.severity)}</span>` : '';
  const message = issue.message || issue.error_message || issue.reason || JSON.stringify(issue, null, 2);
  const meta = [];
  if (issue.file_path) meta.push(`Файл: ${escapeHtml(issue.file_path)}`);
  if (issue.symbol) meta.push(`Символ: ${escapeHtml(issue.symbol)}`);
  if (issue.check_name) meta.push(`Проверка: ${escapeHtml(issue.check_name)}`);

  return `<div class="issue-item">
    <div class="issue-head">${code}${severity}</div>
    <div class="issue-message">${escapeHtml(String(message))}</div>
    ${meta.length ? `<div class="issue-meta">${meta.join('<br>')}</div>` : ''}
  </div>`;
}
function renderArtifact(artifact, kind) {
  if (!artifact?.exists) return '<div class="empty-state">Артефакт отсутствует.</div>';
  const source = kind === 'test' ? artifact.artifact?.source_code : artifact.artifact?.code;
  return `${source ? codeBlock(source) : ''}<details><summary>План и метрики</summary>${jsonBlock({ planner_result: artifact.planner_result, llm_usage: artifact.llm_usage, warnings: artifact.warnings })}</details>`;
}

function bindTabs(root) {
  root.querySelectorAll('.tab-btn').forEach(button => {
    button.addEventListener('click', () => {
      const container = button.closest('.detail-scroll') || root;
      container.querySelectorAll('.tab-btn').forEach(item => item.classList.remove('active'));
      container.querySelectorAll('.tab-panel').forEach(item => item.classList.remove('active'));
      button.classList.add('active');
      const panel = container.querySelector(`#${button.dataset.tab}`);
      if (panel) panel.classList.add('active');
    });
  });
}

async function withBusyButton(button, busyText, action) {
  if (!button) {
    try { return await action(); } catch (error) { alert(error.message); throw error; }
  }
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = busyText;
  try {
    return await action();
  } catch (error) {
    alert(error.message);
    throw error;
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

document.addEventListener('DOMContentLoaded', init);
