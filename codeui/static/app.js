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
function statusBadge(value, kind = '') {
  if (kind) return badge(String(value || '—'), kind);
  const text = String(value || '—');
  const low = text.toLowerCase();
  if (low === 'generated_test_verification_failed') return badge('требуется проверка', 'warn');
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
  if (!cr?.last_run_id || !cr?.last_workspace_id || isFinalCr(cr)) return false;
  const status = String(cr?.status || '').toLowerCase();
  const generateResult = cr?.raw?.last_generate_result || {};
  const summary = generateResult?.result_summary || {};
  const mergePlan = generateResult?.pipeline_result?.merge_plan || generateResult?.merge_plan || {};
  const mergeReady = summary.merge_ready === true || mergePlan.ready_for_manual_merge_review === true;
  return mergeReady || status === 'ready_for_merge_review';
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
function getAnalyzeResult(cr) {
  return cr?.raw?.last_analyze_result || null;
}
function getAnalyzeSummary(cr) {
  const analyze = getAnalyzeResult(cr);
  return analyze?.result_summary || {};
}
function getRequestQuality(cr) {
  const analyze = getAnalyzeResult(cr);
  return analyze?.request_quality || {};
}
function getRequestQualityStatus(cr) {
  return getAnalyzeSummary(cr)?.request_quality_status || getRequestQuality(cr)?.status || '';
}
function getTargetRecommendation(cr) {
  return getAnalyzeResult(cr)?.target_recommendation || {};
}
function getAnalysisUsage(cr) {
  return getAnalyzeResult(cr)?.analysis_usage || getAnalyzeSummary(cr)?.analysis_usage || null;
}
function getOperationSource(cr) {
  return getAnalyzeResult(cr)?.operation_source || getAnalyzeSummary(cr)?.operation_source || '';
}
function getOperationConfidence(cr) {
  return getAnalyzeResult(cr)?.operation_confidence ?? getAnalyzeSummary(cr)?.operation_confidence ?? null;
}
function getDetectedOperation(cr) {
  const analyze = getAnalyzeResult(cr);
  return analyze?.requested_operation || getTargetRecommendation(cr)?.recommended_operation || getAnalyzeSummary(cr)?.requested_operation || null;
}
function getEffectiveOperation(cr) {
  if (cr?.requested_operation) return cr.requested_operation;
  const detected = getDetectedOperation(cr);
  const source = getOperationSource(cr);
  if ((detected === 'replace_symbol' || detected === 'insert_after_symbol') && source !== 'fallback') return detected;
  return null;
}
function getCurrentOperationSelection(cr) {
  const form = $('edit-cr-form');
  if (form && cr?.cr_id === state.selectedCrId) {
    const value = new FormData(form).get('requested_operation');
    return value ? String(value) : null;
  }
  return cr?.requested_operation || null;
}
function getRequiredOperationForAction(cr) {
  const manual = getCurrentOperationSelection(cr) || cr?.requested_operation || null;
  if (manual) return manual;
  const detected = getDetectedOperation(cr);
  const source = getOperationSource(cr);
  if ((detected === 'replace_symbol' || detected === 'insert_after_symbol') && source !== 'fallback') return detected;
  return null;
}
function getEffectiveOperationForAction(cr) {
  return getRequiredOperationForAction(cr);
}
function isRequestInsufficient(cr) {
  return getRequestQualityStatus(cr) === 'insufficient';
}
function isOperationFallback(cr) {
  return getOperationSource(cr) === 'fallback' && !cr?.requested_operation;
}
function getRecommendedOrSelectedTarget(cr) {
  return cr?.selected_target || cr?.recommended_target || getTargetRecommendation(cr)?.recommended_target || null;
}
function canSelectTargetForCr(cr) {
  return Boolean(canWorkWithCr(cr) && cr?.session_id && !isRequestInsufficient(cr) && getRequiredOperationForAction(cr));
}
function canGenerateCr(cr) {
  return Boolean(canWorkWithCr(cr) && cr?.session_id && !isRequestInsufficient(cr) && getRequiredOperationForAction(cr) && getRecommendedOrSelectedTarget(cr));
}
function qualityLabel(value) {
  if (value === 'processable') return 'достаточный';
  if (value === 'uncertain') return 'требует внимания';
  if (value === 'insufficient') return 'недостаточный';
  return value || '—';
}
function operationSourceLabel(value) {
  const map = {
    user: 'выбрана пользователем',
    llm_search_plan: 'определена LLM на этапе плана поиска',
    llm_rerank: 'уточнена LLM после просмотра кандидатов',
    fallback: 'техническое значение по умолчанию',
  };
  return map[value] || value || '—';
}
function targetRoleLabel(value) {
  if (value === 'target') return 'цель изменения';
  if (value === 'anchor') return 'anchor для вставки';
  if (value === 'unknown') return 'не определено';
  return value || '—';
}
function formatConfidence(value) {
  if (value == null || value === '') return '—';
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  return String(Math.round(num * 100) / 100);
}
function renderWarningList(items) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return '';
  return `<div class="message warn-message"><b>Предупреждения:</b><ul>${list.map(item => {
    if (typeof item === 'string') return `<li>${escapeHtml(item)}</li>`;
    return `<li>${item.code ? `<b>${escapeHtml(item.code)}:</b> ` : ''}${escapeHtml(item.message || item.reason || JSON.stringify(item))}</li>`;
  }).join('')}</ul></div>`;
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
      <div class="form-row"><label>Операция</label><select name="requested_operation"><option value="">определить автоматически при анализе</option><option value="replace_symbol">заменить существующий код</option><option value="insert_after_symbol">добавить после существующего кода</option></select></div>
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
      requested_operation: data.get('requested_operation') || null,
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
      <div class="cr-summary-strip">
        <div class="cr-summary-main">
          <span class="cr-summary-code">${escapeHtml(cr.code || '—')}</span>
          <span>${statusBadge(cr.status)}</span>
          <span class="cr-summary-title">${escapeHtml(cr.title || 'Без названия')}</span>
        </div>
        <div class="cr-summary-meta">
          <span>Тех. ID: <span class="mono-text">${escapeHtml(cr.cr_id)}</span></span>
          ${cr.last_run_id ? `<span>Последний запуск: <button class="link-button" id="open-run-inline-btn">${escapeHtml(cr.last_run_id)}</button></span>` : '<span>Последний запуск: —</span>'}
        </div>
      </div>

      <div class="cr-main-grid">
        <div class="card cr-fields-card">
          <h3 class="card-title">Поля запроса</h3>
          ${renderCrEditForm(cr)}
        </div>
        <div class="cr-side-column">
          <div class="card cr-side-card">
            <h3 class="card-title">Связанные требования</h3>
            ${renderCrRequirements(cr)}
          </div>
          <div class="card cr-side-card">
            <h3 class="card-title">Запуски по запросу</h3>
            ${renderCrRuns(cr)}
          </div>
        </div>
      </div>

      <div class="card">
        <h3 class="card-title">Анализ запроса</h3>
        ${renderAnalyzeOverview(cr)}
      </div>
      <div class="card">
        <h3 class="card-title">Действия</h3>
        <div class="action-row">
          <button class="btn" id="analyze-cr-btn" ${!canWorkWithCr(cr) ? 'disabled' : ''}>1. Выполнить анализ</button>
          <button class="btn" id="run-cr-btn" ${!canGenerateCr(cr) ? 'disabled' : ''}>2. Запустить обработку</button>
          ${cr.last_run_id ? '<button class="btn" id="open-run-btn">3. Открыть последний результат</button>' : ''}
          ${canApplyCr(cr) ? '<button class="btn" id="apply-cr-btn">4. Применить последний результат</button>' : ''}
          ${canDeleteCr(cr) ? '<button class="btn danger" id="delete-cr-btn">Удалить запрос</button>' : ''}
        </div>
      </div>
      <div class="tabs">
        <button class="tab-btn active" data-tab="cr-candidates">Место изменения</button>
        <button class="tab-btn" data-tab="cr-analysis-usage">Статистика</button>
        <button class="tab-btn" data-tab="cr-json">JSON</button>
      </div>
      <div id="cr-candidates" class="tab-panel active">${renderCandidates(candidates, cr)}</div>
      <div id="cr-analysis-usage" class="tab-panel">${renderAnalyzeUsage(cr)}</div>
      <div id="cr-json" class="tab-panel">${jsonBlock(cr)}</div>
    </div>
  `;
  bindTabs($('cr-detail'));
  bindCrEditForm(cr);
  $('analyze-cr-btn').addEventListener('click', event => analyzeCr(cr.cr_id, event.currentTarget));
  $('run-cr-btn').addEventListener('click', event => runCr(cr.cr_id, event.currentTarget));
  const openRun = $('open-run-btn');
  if (openRun) openRun.addEventListener('click', () => openRunView(cr.last_run_id));
  const openRunInline = $('open-run-inline-btn');
  if (openRunInline) openRunInline.addEventListener('click', () => openRunView(cr.last_run_id));
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
        <option value="" ${!cr.requested_operation ? 'selected' : ''}>определить автоматически при анализе</option>
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
  const operationSelect = form.querySelector('[name="requested_operation"]');
  if (operationSelect) {
    operationSelect.addEventListener('change', () => {
      const value = operationSelect.value || null;
      cr.requested_operation = value;
      if (!cr.raw || typeof cr.raw !== 'object') cr.raw = {};
      cr.raw.operation_selection_source = value ? 'user' : 'none';
      renderSelectedCr();
    });
  }
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
      requested_operation: data.get('requested_operation') || null,
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

function renderAnalyzeOverview(cr) {
  const analyze = getAnalyzeResult(cr);
  if (!analyze) return '<div class="empty-state">Анализ еще не выполнялся.</div>';
  return `
    <div class="analysis-grid">
      ${renderQualitySummary(cr)}
      ${renderOperationSummary(cr)}
      ${renderTargetRecommendationSummary(cr)}
    </div>
  `;
}

function renderQualitySummary(cr) {
  const quality = getRequestQuality(cr);
  const status = getRequestQualityStatus(cr);
  const missing = Array.isArray(quality.missing_information) ? quality.missing_information : [];
  const statusKind = status === 'insufficient' ? 'err' : status === 'uncertain' ? 'warn' : status === 'processable' ? 'ok' : '';
  return `<div class="analysis-box">
    <div class="analysis-title">Качество запроса</div>
    <div>${badge(qualityLabel(status), statusKind)}</div>
    ${quality.reason ? `<div class="analysis-text">${escapeHtml(quality.reason)}</div>` : ''}
    ${missing.length ? `<div class="compact-list-title">Нужно уточнить</div><ul>${missing.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}
    ${status === 'insufficient' ? '<div class="message warn-message">Измените название, описание или ограничения и выполните анализ заново. Генерация заблокирована.</div>' : ''}
  </div>`;
}

function renderOperationSummary(cr) {
  const selectedOperation = cr.requested_operation;
  const detected = getDetectedOperation(cr);
  const source = getOperationSource(cr);
  const confidence = getOperationConfidence(cr);
  const analyze = getAnalyzeResult(cr) || {};
  const reason = analyze.operation_reason || getTargetRecommendation(cr).operation_reason || '';
  const reliable = Boolean(selectedOperation);
  const operationSelectionSource = cr.raw?.operation_selection_source || '';
  const sourceForDisplay = source === 'user' && operationSelectionSource !== 'user' ? '' : source;
  const modeText = selectedOperation
    ? (operationSelectionSource === 'analysis' ? 'автоматически' : 'выбрана вручную')
    : 'не выбрана';
  const recommendationText = detected ? operationLabel(detected) : '—';
  return `<div class="analysis-box">
    <div class="analysis-title">Операция</div>
    <div class="kv-grid compact-kv mini-kv">
      <div class="key">Режим</div><div>${escapeHtml(modeText)}</div>
      ${selectedOperation ? `<div class="key">Выбор</div><div>${escapeHtml(operationLabel(selectedOperation))}</div>` : ''}
      <div class="key">Рекомендация</div><div>${escapeHtml(recommendationText)} ${sourceForDisplay ? badge(operationSourceLabel(sourceForDisplay), sourceForDisplay === 'fallback' ? 'warn' : 'info') : ''}</div>
      <div class="key">Уверенность</div><div>${escapeHtml(formatConfidence(confidence))}</div>
    </div>
    ${reason ? `<div class="analysis-text">${escapeHtml(reason)}</div>` : ''}
    ${!reliable ? '<div class="message warn-message">Операция не выбрана. Перед запуском обработки выберите операцию.</div>' : ''}
  </div>`;
}

function renderTargetRecommendationSummary(cr) {
  const recommendation = getTargetRecommendation(cr);
  const target = recommendation.recommended_target || cr.recommended_target;
  const role = recommendation.target_role || '';
  const confidence = recommendation.target_confidence ?? getAnalyzeSummary(cr).target_selection_confidence;
  const manualReview = Boolean(recommendation.manual_review_required || getAnalyzeSummary(cr).manual_review_required);
  const source = getAnalyzeSummary(cr).target_selection_source;
  const post = recommendation.post_processing;
  return `<div class="analysis-box">
    <div class="analysis-title">Рекомендация места</div>
    <div class="kv-grid compact-kv mini-kv">
      <div class="key">Место</div><div class="mono-text">${escapeHtml(target || '—')}</div>
      <div class="key">Роль</div><div>${badge(targetRoleLabel(role), role === 'anchor' ? 'blue' : role === 'target' ? 'ok' : 'warn')}</div>
      <div class="key">Источник</div><div>${escapeHtml(source || '—')}</div>
      <div class="key">Уверенность</div><div>${escapeHtml(formatConfidence(confidence))}</div>
      <div class="key">Проверка</div><div>${manualReview ? statusBadge('требуется') : statusBadge('не требуется', 'ok')}</div>
    </div>
    ${recommendation.target_reason ? `<div class="analysis-text">${escapeHtml(recommendation.target_reason)}</div>` : ''}
    ${post ? `<div class="message compact-message">Anchor скорректирован: ${escapeHtml(post.original_recommended_target || '—')} → ${escapeHtml(post.recommended_target || '—')}</div>` : ''}
    ${renderWarningList(recommendation.warnings || getAnalyzeResult(cr)?.warnings)}
  </div>`;
}

function renderAnalyzeUsage(cr) {
  const usage = getAnalysisUsage(cr);
  if (!usage) return '<div class="empty-state">Статистика анализа отсутствует.</div>';
  const steps = usage.steps || {};
  const rows = [
    analyzeUsageRow('Всего', usage),
    steps.search_plan ? analyzeUsageRow('План поиска', steps.search_plan) : '',
    steps.candidate_rerank ? analyzeUsageRow('Ранжирование кандидатов', steps.candidate_rerank) : '',
  ].filter(Boolean).join('');
  return `<div class="stats-stack">
    <div class="stats-title">LLM-вызовы</div>
    <table class="table compact-usage-table"><thead><tr><th>Этап</th><th>Вызовы</th><th>Prompt</th><th>Output</th><th>Total</th><th>Символы prompt</th><th>Длительность</th></tr></thead><tbody>${rows}</tbody></table>
    ${renderAnalyzeTimingTable(usage)}
  </div>`;
}

function analyzeUsageRow(title, usage) {
  const calls = title === 'Всего' ? usage.calls : 1;
  return `<tr>
    <td>${escapeHtml(title)}</td>
    <td>${escapeHtml(calls ?? '—')}</td>
    <td>${escapeHtml(usage.prompt_tokens ?? '—')}</td>
    <td>${escapeHtml(usage.output_tokens ?? '—')}</td>
    <td>${escapeHtml(usage.total_tokens ?? '—')}</td>
    <td>${escapeHtml(usage.prompt_chars ?? '—')}</td>
    <td>${usage.duration_sec != null ? `${escapeHtml(formatNumber(usage.duration_sec))} c` : '—'}</td>
  </tr>`;
}

function renderAnalyzeTimingTable(usage) {
  const timings = usage?.timings || {};
  const steps = usage?.steps || {};
  const rows = [];
  const push = (key, title, comment = '') => {
    if (timings[key] == null) return;
    rows.push(timingRow(title, timings[key], comment));
  };

  push('search_plan_total_sec', 'План поиска: всего', 'LLM-вызов и служебная обработка search plan');
  push('session_create_sec', 'Создание сессии', 'Запись состояния analyze-сессии');
  push('recall_search_sec', 'Поиск кандидатов', 'Поиск по индексу и embedding-запросы');
  push('candidate_rerank_total_sec', 'Ранжирование: всего', 'Подготовка candidate cards, prompt и LLM rerank');

  const rerankTotal = Number(timings.candidate_rerank_total_sec);
  const rerankLlm = Number(steps.candidate_rerank?.duration_sec);
  if (Number.isFinite(rerankTotal) && Number.isFinite(rerankLlm)) {
    const overhead = Math.max(0, rerankTotal - rerankLlm);
    rows.push(timingRow('Подготовка rerank', overhead, 'candidate cards, context и prompt вокруг LLM rerank'));
  }

  push('target_resolution_sec', 'Определение места', 'Post-processing target или anchor');
  push('api_candidates_sec', 'Кандидаты для API', 'Подготовка списка кандидатов для ответа');
  push('context_summary_sec', 'Context summary', 'Сбор краткого контекста для рекомендованного места');
  push('total_sec', 'Analyze: всего', 'Полная длительность analyze');

  if (!rows.length) return '';
  return `<div class="stats-title">Runtime-этапы analyze</div>
    <table class="table compact-usage-table"><thead><tr><th>Этап</th><th>Время</th><th>Комментарий</th></tr></thead><tbody>${rows.join('')}</tbody></table>`;
}

function timingRow(title, seconds, comment = '') {
  return `<tr>
    <td>${escapeHtml(title)}</td>
    <td>${seconds != null ? `${escapeHtml(formatNumber(seconds))} c` : '—'}</td>
    <td>${escapeHtml(comment || '—')}</td>
  </tr>`;
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
  return `${manualBlock}<table class="table candidates-table"><thead><tr><th>Ранг</th><th>Место изменения</th><th>Тип</th><th>Оценка</th><th>LLM</th><th>Причины</th><th></th></tr></thead><tbody>${candidates.map(candidate => {
    const llmBadge = candidate.llm_recommended ? badge('рекомендовано', 'ok') : candidate.ranked_by_llm ? badge(`LLM #${candidate.llm_rank || '—'}`, 'info') : badge('поиск');
    const scoreText = [candidate.relevance_category, candidate.confidence != null ? `увер. ${formatConfidence(candidate.confidence)}` : '', candidate.score != null ? `score ${candidate.score}` : ''].filter(Boolean).join('<br>');
    const reasons = [candidate.llm_reason ? `LLM: ${candidate.llm_reason}` : '', ...(candidate.reasons || []).slice(0, 4)].filter(Boolean);
    return `
    <tr>
      <td>${candidate.llm_rank != null ? escapeHtml(candidate.llm_rank) : '—'}</td>
      <td><b>${escapeHtml(candidate.name || '')}</b><br><span class="item-meta mono-text">${escapeHtml(candidate.qualname)}</span><br><span class="item-meta">${escapeHtml(candidate.file_path)}</span></td>
      <td>${escapeHtml(candidate.kind || '—')}</td>
      <td>${scoreText}</td>
      <td>${llmBadge}</td>
      <td>${reasons.map(escapeHtml).join('<br>')}</td>
      <td><button class="btn small ${cr.selected_target === candidate.qualname ? 'selected' : ''}" data-select-target="${escapeHtml(candidate.qualname)}" ${!canSelectTargetForCr(cr) ? 'disabled' : ''}>Выбрать</button></td>
    </tr>`;
  }).join('')}</tbody></table>`;
}

function renderManualTargetBlock(cr) {
  const disabled = !canSelectTargetForCr(cr);
  let hint = 'Укажите полное имя символа, если нужного варианта нет в списке.';
  if (!cr.session_id) hint = 'Ручной выбор будет доступен после анализа запроса.';
  else if (isRequestInsufficient(cr)) hint = 'Запрос недостаточно конкретный. Измените запрос и выполните анализ заново.';
  else if (!getRequiredOperationForAction(cr)) hint = 'Перед ручным выбором укажите операцию.';
  const role = getRequiredOperationForAction(cr) === 'insert_after_symbol' ? 'Anchor для вставки' : 'Место изменения';
  return `
    <div class="manual-target-panel">
      <div class="form-row"><label>${escapeHtml(role)}</label><input id="manual-target-input" value="${escapeHtml(getRecommendedOrSelectedTarget(cr) || '')}" placeholder="package.module.Class.method" ${disabled ? 'disabled' : ''}></div>
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
  renderSelectedRequirementDetailIfVisible();
  if (reloadRuns) renderRuns();
}

function renderSelectedRequirementDetailIfVisible() {
  if (!state.selectedRequirementId) return;
  const requirement = state.requirements.find(item => item.id === state.selectedRequirementId);
  if (requirement) renderRequirementDetail(requirement);
}

function upsertChangeRequest(updatedCr) {
  if (!updatedCr || !updatedCr.cr_id) return;
  const index = state.changeRequests.findIndex(item => item.cr_id === updatedCr.cr_id);
  if (index >= 0) state.changeRequests[index] = updatedCr;
  else state.changeRequests.unshift(updatedCr);
  state.selectedCrId = updatedCr.cr_id;
}

async function analyzeCr(crId, button) {
  if (state.busy.has(crId)) return;
  const cr = state.changeRequests.find(item => item.cr_id === crId);
  state.busy.add(crId);
  const operation = getCurrentOperationSelection(cr);
  if (cr) {
    cr.requested_operation = operation;
    clearLocalAnalyzeState(cr);
    cr.status = 'analyzing';
    renderCrList();
    renderSelectedCr();
  }
  let response = null;
  try {
    response = await api.post(`/api/change-requests/${encodeURIComponent(crId)}/analyze`, { operation });
  } finally {
    state.busy.delete(crId);
  }
  if (response?.change_request) {
    upsertChangeRequest(response.change_request);
    renderCrList();
    renderSelectedCr();
    renderSelectedRequirementDetailIfVisible();
  }
  await refreshCrAfterAction();
}

function clearLocalAnalyzeState(cr) {
  cr.session_id = null;
  cr.recommended_target = null;
  cr.selected_target = null;
  cr.last_run_id = null;
  cr.last_workspace_id = null;
  if (!cr.raw || typeof cr.raw !== 'object') cr.raw = {};
  delete cr.raw.last_analyze_result;
  delete cr.raw.last_select_result;
  delete cr.raw.last_generate_result;
  delete cr.raw.last_error;
}
async function selectTarget(crId, qualname, button) {
  if (state.busy.has(crId)) return;
  const cr = state.changeRequests.find(item => item.cr_id === crId);
  if (isRequestInsufficient(cr)) {
    alert('Запрос недостаточно конкретный. Измените запрос и выполните анализ заново.');
    return;
  }
  const operation = getEffectiveOperationForAction(cr);
  if (!operation) {
    alert('Операция не выбрана. Заполните поле «Операция» перед выбором места изменения.');
    return;
  }
  state.busy.add(crId);
  try {
    await withBusyButton(button, 'Выбор...', async () => {
      await api.post(`/api/change-requests/${encodeURIComponent(crId)}/select-target`, { selected_qualname: qualname, operation });
    });
  } finally {
    state.busy.delete(crId);
    await refreshCrAfterAction();
  }
}
async function runCr(crId, button) {
  if (state.busy.has(crId)) return;
  const cr = state.changeRequests.find(item => item.cr_id === crId);
  if (!canGenerateCr(cr)) {
    if (isRequestInsufficient(cr)) alert('Генерация заблокирована: запрос недостаточно конкретный. Измените запрос и выполните анализ заново.');
    else if (!getRequiredOperationForAction(cr)) alert('Генерация заблокирована: заполните поле «Операция».');
    else if (!getRecommendedOrSelectedTarget(cr)) alert('Генерация заблокирована: не выбрано место изменения.');
    return;
  }
  state.busy.add(crId);
  try {
    await withBusyButton(button, 'Выполняется...', async () => {
      const result = await api.post(`/api/change-requests/${encodeURIComponent(crId)}/run`, { operation: getRequiredOperationForAction(cr) });
      const blocked = result?.generate_result?.result_summary?.generation_blocked;
      if (blocked) alert(result.generate_result.result_summary.message || 'Генерация заблокирована.');
    });
  } finally {
    state.busy.delete(crId);
    await refreshCrAfterAction({ reloadRuns: true });
  }
}
async function applyLastRun(crId, button) {
  if (!confirm('Применить последний результат в основной проект?')) return;
  await withBusyButton(button, 'Применение...', async () => {
    const result = await api.post(`/api/change-requests/${encodeURIComponent(crId)}/apply-last-run`, {});
    showApplyResultMessage(result?.apply_result);
    await Promise.all([loadChangeRequests(), loadRuns()]);
    renderCrList();
    renderSelectedCr();
    renderSelectedRequirementDetailIfVisible();
    renderRuns();
  });
}

function showApplyResultMessage(result) {
  if (!result || typeof result !== 'object') return;
  const applied = Array.isArray(result.applied_files) ? result.applied_files : [];
  const excluded = Array.isArray(result.excluded_files) ? result.excluded_files : [];
  if (!applied.length && !excluded.length) return;
  const lines = [];
  if (applied.length) lines.push(`Применено:
- ${applied.join('\n- ')}`);
  if (excluded.length) lines.push(`Не применено:
- ${excluded.join('\n- ')}`);
  alert(lines.join('\n\n'));
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
        <div class="run-main-grid">
          <div class="card"><h3 class="card-title">Результат запуска</h3>${renderRunSummary(summary)}</div>
          ${renderRunContext(runId)}
        </div>
        <div class="tabs">
          <button class="tab-btn active" data-tab="run-steps">Шаги</button>
          <button class="tab-btn" data-tab="run-checks">Проверки</button>
          <button class="tab-btn" data-tab="run-apply">Применение</button>
          <button class="tab-btn" data-tab="run-resources">Статистика</button>
          <button class="tab-btn" data-tab="run-diff">Diff</button>
          <button class="tab-btn" data-tab="run-code">Код</button>
          <button class="tab-btn" data-tab="run-test">Тест</button>
        </div>
        <div id="run-steps" class="tab-panel active">${renderSteps(steps)}</div>
        <div id="run-checks" class="tab-panel">${renderChecks(checks, summary)}</div>
        <div id="run-apply" class="tab-panel">${renderApplyPlan(summary)}</div>
        <div id="run-resources" class="tab-panel">${renderResources(summary)}</div>
        <div id="run-diff" class="tab-panel">${renderDiff(diff)}</div>
        <div id="run-code" class="tab-panel">${renderArtifact(code, 'code')}</div>
        <div id="run-test" class="tab-panel">${renderArtifact(test, 'test', summary)}</div>
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
  const mainIssue = summary.primary_issue ? renderPrimaryIssue(summary.primary_issue) : '';
  const partialGeneratedTest = summary.status === 'generated_test_verification_failed' || summary.generated_test_failed === true || summary.generated_test_verification_failed === true;
  const productionState = partialGeneratedTest && summary.production_failed === false ? statusBadge('готов к review', 'ok') : (summary.verification_passed ? statusBadge('без ошибок', 'ok') : statusBadge('требует проверки', 'warn'));
  const generatedTestState = summary.generated_test_failed || summary.generated_test_verification_failed
    ? statusBadge('не прошел проверку', 'warn')
    : summary.has_generated_test ? statusBadge('сгенерирован', 'ok') : statusBadge('нет');
  return `<div class="compact-summary">
    ${partialGeneratedTest ? `<div class="message warning-message"><b>Результат требует ручной проверки.</b> Основной код можно рассматривать для применения, но сгенерированный тест не прошел проверку и будет исключен из применения.</div>` : ''}
    <div class="kv-grid compact-kv">
      <div class="key">Статус</div><div>${statusBadge(summary.status)}</div>
      <div class="key">Операция</div><div>${escapeHtml(summary.final_operation || summary.requested_operation || '—')}</div>
      <div class="key">Место изменения</div><div class="mono-text">${escapeHtml(summary.selected_target || '—')}</div>
      <div class="key">Production-код</div><div>${productionState}</div>
      <div class="key">Generated test</div><div>${generatedTestState}</div>
      <div class="key">Repair</div><div>${summary.repair_used ? statusBadge('использовался', 'warn') : statusBadge('нет')}</div>
      <div class="key">Применение</div><div>${summary.merge_ready ? statusBadge('готово', 'ok') : statusBadge('не готово', 'warn')}</div>
      <div class="key">Рабочая копия</div><div class="path-text">${escapeHtml(summary.workspace_path || '—')}</div>
    </div>
    ${mainIssue}
    <div class="summary-columns">
      ${renderCompactList('Файлы к применению', summary.changed_files)}
      ${renderCompactList('Исключены из применения', summary.excluded_files)}
      ${renderCompactList('Символы', summary.symbols_in_changed_files)}
      ${renderCompactList('Требования', summary.linked_requirements)}
      ${renderCompactList('Тестовые команды', summary.recommended_test_commands)}
      ${renderCompactList('Проблемные generated tests', summary.generated_test_failed_files)}
    </div>
  </div>`;
}

function renderPrimaryIssue(issue) {
  const parts = [];
  if (issue.check_name) parts.push(`Проверка: ${escapeHtml(issue.check_name)}`);
  if (issue.code) parts.push(`Код: ${escapeHtml(issue.code)}`);
  if (issue.file_path) parts.push(`Файл: ${escapeHtml(issue.file_path)}`);
  if (issue.symbol) parts.push(`Символ: ${escapeHtml(issue.symbol)}`);
  return `<div class="primary-issue">
    <div class="primary-issue-title">Основная проблема</div>
    <div class="primary-issue-message">${escapeHtml(issue.message || 'Причина не указана')}</div>
    ${parts.length ? `<div class="primary-issue-meta">${parts.join('<br>')}</div>` : ''}
  </div>`;
}

function renderCompactList(title, values) {
  const items = Array.isArray(values) ? values.filter(Boolean) : [];
  return `<div class="compact-list-block">
    <div class="compact-list-title">${escapeHtml(title)}</div>
    ${items.length ? `<ul>${items.slice(0, 8).map(value => `<li>${escapeHtml(value)}</li>`).join('')}${items.length > 8 ? `<li>и еще ${items.length - 8}</li>` : ''}</ul>` : '<span class="muted">—</span>'}
  </div>`;
}

function renderApplyPlan(summary) {
  const lines = Array.isArray(summary.merge_plan_summary_lines) ? summary.merge_plan_summary_lines : [];
  return `<div class="compact-section">
    <div class="kv-grid compact-kv">
      <div class="key">Режим</div><div>${escapeHtml(summary.merge_mode || '—')}</div>
      <div class="key">Готов к применению</div><div>${summary.merge_ready ? statusBadge('да', 'ok') : statusBadge('нет', 'warn')}</div>
      <div class="key">Рабочая копия</div><div class="path-text">${escapeHtml(summary.workspace_path || '—')}</div>
      <div class="key">Generated test</div><div>${summary.generated_test_merge_recommended === false ? statusBadge('исключен', 'warn') : summary.generated_test_failed ? statusBadge('ошибка', 'warn') : statusBadge('—')}</div>
    </div>
    <div class="summary-columns">
      ${renderCompactList('Файлы к применению', summary.changed_files)}
      ${renderCompactList('Исключены из применения', summary.excluded_files)}
      ${renderCompactList('Символы', summary.symbols_in_changed_files)}
      ${renderCompactList('Связанные требования', summary.linked_requirements)}
      ${renderCompactList('Рекомендуемые проверки', summary.recommended_test_commands)}
    </div>
    ${lines.length ? `<div class="compact-list-block full-width"><div class="compact-list-title">Комментарий</div><ul>${lines.map(line => `<li>${escapeHtml(line)}</li>`).join('')}</ul></div>` : ''}
    ${(summary.warnings || []).length ? `<div class="compact-list-block full-width"><div class="compact-list-title">Предупреждения</div><ul>${summary.warnings.map(line => `<li>${escapeHtml(line)}</li>`).join('')}</ul></div>` : ''}
  </div>`;
}


function renderDiff(diff) {
  const excluded = Array.isArray(diff?.excluded_files) ? diff.excluded_files : [];
  const changed = Array.isArray(diff?.changed_files) ? diff.changed_files : [];
  return `<div class="compact-section">
    ${renderCompactList('Файлы в diff', changed)}
    ${excluded.length ? renderCompactList('Исключены из применения', excluded) : ''}
    ${excluded.length ? '<div class="message compact-message">Diff для review фильтруется с учетом исключенных файлов, если backend передал excluded_files.</div>' : ''}
    ${codeBlock(diff?.unified_diff || '')}
  </div>`;
}

function renderResources(summary) {
  const rows = [
    usageRow('Генерация кода', summary.code_generation_usage),
    usageRow('Генерация теста', summary.test_generation_usage),
    usageRow('Repair', summary.repair_generation_usage),
    usageRow('Embeddings', summary.embedding_usage, true),
  ].filter(Boolean).join('');
  if (!rows) return '<div class="empty-state">Usage-метрики для этого запуска отсутствуют.</div>';
  return `<table class="table compact-usage-table"><thead><tr><th>Этап</th><th>Вызовы</th><th>Prompt</th><th>Output</th><th>Total</th><th>Длительность</th><th>Дополнительно</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function usageRow(title, usage, embedding = false) {
  if (!usage || typeof usage !== 'object') return '';
  const duration = usage.duration_sec ?? usage.total_duration_sec;
  const extra = embedding
    ? [
        usage.texts_count != null ? `Текстов: ${usage.texts_count}` : '',
        usage.chars_total != null ? `Символов: ${usage.chars_total}` : '',
        Array.isArray(usage.models) ? `Модель: ${usage.models.join(', ')}` : '',
      ].filter(Boolean).join('<br>')
    : [
        usage.total_duration_sec != null ? `Всего: ${formatNumber(usage.total_duration_sec)} c` : '',
        usage.load_duration_sec != null ? `Load: ${formatNumber(usage.load_duration_sec)} c` : '',
      ].filter(Boolean).join('<br>');
  return `<tr>
    <td>${escapeHtml(title)}</td>
    <td>${escapeHtml(usage.calls ?? '—')}</td>
    <td>${escapeHtml(usage.prompt_tokens ?? '—')}</td>
    <td>${escapeHtml(usage.output_tokens ?? '—')}</td>
    <td>${escapeHtml(usage.total_tokens ?? usage.prompt_tokens ?? '—')}</td>
    <td>${duration != null ? `${escapeHtml(formatNumber(duration))} c` : '—'}</td>
    <td>${extra || '—'}</td>
  </tr>`;
}

function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value ?? '');
  return Math.round(number * 100) / 100;
}
function renderSteps(steps) {
  return `<table class="table"><thead><tr><th>Шаг</th><th>Статус</th><th>Время</th><th>Токены</th><th>Описание</th></tr></thead><tbody>${(steps || []).map(step => `
    <tr><td>${escapeHtml(step.step_name)}</td><td>${statusBadge(step.status)}</td><td>${escapeHtml(step.duration_ms ?? '—')} мс</td><td>${escapeHtml(step.usage?.total_tokens ?? '—')}</td><td>${escapeHtml(step.summary || '')}</td></tr>
  `).join('')}</tbody></table>`;
}
function renderChecks(checks, summary = null) {
  const note = summary && (summary.status === 'generated_test_verification_failed' || summary.generated_test_failed === true)
    ? '<div class="message warning-message">Ошибка относится к сгенерированному тесту. Основной production-код не классифицирован как ошибочный.</div>'
    : '';
  return note + `<table class="table checks-table"><thead><tr><th>Проверка</th><th>Результат</th><th>Уровень</th><th>Проблемы</th></tr></thead><tbody>${(checks || []).map(check => `
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
function renderArtifact(artifact, kind, summary = null) {
  if (!artifact?.exists) return '<div class="empty-state">Артефакт отсутствует.</div>';
  const source = kind === 'test' ? artifact.artifact?.source_code : artifact.artifact?.code;
  const testNote = kind === 'test' && summary && (summary.generated_test_failed || summary.generated_test_verification_failed || summary.generated_test_merge_recommended === false)
    ? `<div class="message warning-message">Сгенерированный тест создан, но не рекомендован к применению.${renderCompactList('Исключенные test-файлы', summary.generated_test_excluded_files || summary.excluded_files || [])}</div>`
    : '';
  return `${testNote}${source ? codeBlock(source) : ''}<details><summary>План и метрики</summary>${jsonBlock({ planner_result: artifact.planner_result, llm_usage: artifact.llm_usage, warnings: artifact.warnings })}</details>`;
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
