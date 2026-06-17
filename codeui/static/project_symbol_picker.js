(function () {
  const DEFAULT_ENDPOINT = '/api/project-schema';
  let activeModal = null;
  let keydownHandler = null;

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
  }

  function shortText(value, len = 140) {
    const text = String(value || '').replace(/\s+/g, ' ').trim();
    return text.length > len ? `${text.slice(0, len)}…` : text;
  }

  function kindIcon(kind) {
    if (kind === 'package') return '📦';
    if (kind === 'module') return '◫';
    if (kind === 'class') return 'C';
    if (kind === 'member') return 'ƒ';
    return '•';
  }

  function kindTitle(kind) {
    if (kind === 'package') return 'package';
    if (kind === 'module') return 'module';
    if (kind === 'class') return 'class';
    if (kind === 'member') return 'class member / method';
    return 'symbol';
  }

  function kindBadge(kind) {
    const normalized = kind || 'symbol';
    return `<span class="symbol-picker-kind ${escapeHtml(normalized)}" title="${escapeHtml(kindTitle(normalized))}">${escapeHtml(kindIcon(normalized))}</span>`;
  }

  function kindRank(kind) {
    if (kind === 'package') return 0;
    if (kind === 'module') return 1;
    if (kind === 'class') return 2;
    if (kind === 'member') return 3;
    return 4;
  }

  function compareNodes(a, b) {
    const ak = kindRank(a.kind);
    const bk = kindRank(b.kind);
    if (ak !== bk) return ak - bk;
    return String(a.id).localeCompare(String(b.id));
  }

  function buildChildren(nodes) {
    const sorted = [...nodes].sort(compareNodes);
    const result = new Map();
    for (const node of sorted) {
      const parent = node.parent_id || null;
      if (!result.has(parent)) result.set(parent, []);
      result.get(parent).push(node);
    }
    return result;
  }

  function flattenTree(nodes) {
    const children = buildChildren(nodes);
    const roots = (children.get(null) || []).concat(children.get('') || []);
    const rows = [];
    const rendered = new Set();

    function visit(node, level) {
      rows.push({ node, level });
      rendered.add(node.id);
      for (const child of children.get(node.id) || []) {
        visit(child, level + 1);
      }
    }

    for (const root of roots) visit(root, 0);
    for (const node of [...nodes].sort(compareNodes)) {
      if (!rendered.has(node.id)) rows.push({ node, level: 0 });
    }
    return rows;
  }

  function searchText(node) {
    return [node.id, node.label, node.title, node.description, node.kind]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
  }

  function filterRows(rows, query) {
    const normalizedQuery = String(query || '').trim().toLowerCase();
    if (!normalizedQuery) return rows;

    const nodeById = new Map(rows.map(row => [row.node.id, row.node]));
    const visibleIds = new Set();
    for (const row of rows) {
      if (!searchText(row.node).includes(normalizedQuery)) continue;
      let current = row.node;
      while (current && !visibleIds.has(current.id)) {
        visibleIds.add(current.id);
        current = current.parent_id ? nodeById.get(current.parent_id) : null;
      }
    }
    return rows.filter(row => visibleIds.has(row.node.id));
  }

  function isSelectableNode(node) {
    return Boolean(node && node.id && node.kind !== 'package');
  }

  async function fetchSchema(endpoint) {
    const response = await fetch(endpoint || DEFAULT_ENDPOINT);
    const text = await response.text();
    let payload = null;
    if (text) {
      try { payload = JSON.parse(text); } catch (_) { payload = text; }
    }
    if (!response.ok) {
      const message = payload?.error?.message || payload?.message || payload?.detail || text || `HTTP ${response.status}`;
      throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
    }
    return payload;
  }

  function close() {
    if (activeModal) {
      activeModal.remove();
      activeModal = null;
    }
    if (keydownHandler) {
      document.removeEventListener('keydown', keydownHandler);
      keydownHandler = null;
    }
    document.body.classList.remove('symbol-picker-open');
  }

  function createShell(title) {
    close();
    const overlay = document.createElement('div');
    overlay.className = 'symbol-picker-backdrop';
    overlay.innerHTML = `
      <div class="symbol-picker-modal" role="dialog" aria-modal="true" aria-label="${escapeHtml(title || 'Выбор элемента проекта')}">
        <div class="symbol-picker-header">
          <div>
            <div class="symbol-picker-title">${escapeHtml(title || 'Выбор элемента проекта')}</div>
            <div class="symbol-picker-subtitle">Выберите module, class, function или method. В поле будет записано полное имя.</div>
          </div>
          <button class="btn small symbol-picker-close" type="button" aria-label="Закрыть">×</button>
        </div>
        <div class="symbol-picker-toolbar">
          <input class="symbol-picker-search" type="search" placeholder="Поиск по имени или полному пути" autocomplete="off">
        </div>
        <div class="symbol-picker-body">
          <div class="empty-state">Загрузка схемы проекта...</div>
        </div>
        <div class="symbol-picker-footer">
          <div class="symbol-picker-selected"><span class="muted">Выбрано:</span> <span class="symbol-picker-selected-value">—</span></div>
          <div class="action-row">
            <button class="btn small symbol-picker-cancel" type="button">Отмена</button>
            <button class="btn small primary symbol-picker-submit" type="button" disabled>Выбрать</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    document.body.classList.add('symbol-picker-open');
    activeModal = overlay;
    overlay.addEventListener('mousedown', event => {
      if (event.target === overlay) close();
    });
    overlay.querySelector('.symbol-picker-close')?.addEventListener('click', close);
    overlay.querySelector('.symbol-picker-cancel')?.addEventListener('click', close);
    keydownHandler = event => {
      if (event.key === 'Escape') close();
    };
    document.addEventListener('keydown', keydownHandler);
    return overlay;
  }

  function renderRows(body, rows, state) {
    if (!rows.length) {
      body.innerHTML = '<div class="empty-state">Ничего не найдено.</div>';
      return;
    }
    body.innerHTML = `<div class="symbol-picker-tree">${rows.map(row => renderRow(row, state.selectedId)).join('')}</div>`;
    body.querySelectorAll('[data-symbol-id]').forEach(element => {
      element.addEventListener('click', () => {
        const id = element.dataset.symbolId;
        const node = state.nodeById.get(id);
        if (!isSelectableNode(node)) return;
        state.selectedId = id;
        updateSelection(body.closest('.symbol-picker-backdrop'), state);
        renderRows(body, rows, state);
      });
      element.addEventListener('dblclick', () => {
        const id = element.dataset.symbolId;
        const node = state.nodeById.get(id);
        if (!isSelectableNode(node)) return;
        state.selectedId = id;
        submitSelection(state);
      });
    });
  }

  function renderRow(row, selectedId) {
    const node = row.node;
    const selectable = isSelectableNode(node);
    const selected = node.id === selectedId;
    const indent = Math.min(row.level, 12) * 16;
    const subtitle = node.title && node.title !== node.label ? node.title : '';
    return `
      <div class="symbol-picker-row ${selectable ? 'is-selectable' : 'is-disabled'} ${selected ? 'is-selected' : ''}" data-symbol-id="${escapeHtml(node.id)}" style="padding-left:${indent}px" title="${escapeHtml(node.id)}">
        ${kindBadge(node.kind)}
        <span class="symbol-picker-label">${escapeHtml(node.label || node.id)}</span>
        <span class="symbol-picker-path">${escapeHtml(node.id)}</span>
        ${subtitle ? `<span class="symbol-picker-node-title">${escapeHtml(shortText(subtitle, 90))}</span>` : ''}
      </div>
    `;
  }

  function updateSelection(overlay, state) {
    const node = state.nodeById.get(state.selectedId);
    const value = overlay.querySelector('.symbol-picker-selected-value');
    const submit = overlay.querySelector('.symbol-picker-submit');
    if (value) value.textContent = node?.id || '—';
    if (submit) submit.disabled = !isSelectableNode(node);
  }

  function submitSelection(state) {
    const node = state.nodeById.get(state.selectedId);
    if (!isSelectableNode(node)) return;
    if (typeof state.onSelect === 'function') state.onSelect(node);
    close();
  }

  async function open(options = {}) {
    const overlay = createShell(options.title || 'Выбор места изменения');
    const body = overlay.querySelector('.symbol-picker-body');
    const search = overlay.querySelector('.symbol-picker-search');
    const submit = overlay.querySelector('.symbol-picker-submit');
    const state = {
      onSelect: options.onSelect,
      selectedId: String(options.selectedId || '').trim(),
      rows: [],
      nodeById: new Map(),
    };

    try {
      const schema = options.schema || await fetchSchema(options.endpoint || DEFAULT_ENDPOINT);
      const nodes = Array.isArray(schema?.nodes) ? schema.nodes : [];
      state.nodeById = new Map(nodes.map(node => [node.id, node]));
      state.rows = flattenTree(nodes);
      if (!isSelectableNode(state.nodeById.get(state.selectedId))) state.selectedId = '';
      renderRows(body, state.rows, state);
      updateSelection(overlay, state);
      search?.focus();
    } catch (error) {
      body.innerHTML = `<div class="empty-state">Не удалось загрузить схему проекта: ${escapeHtml(error.message || error)}</div>`;
    }

    search?.addEventListener('input', () => {
      const visibleRows = filterRows(state.rows, search.value);
      renderRows(body, visibleRows, state);
      updateSelection(overlay, state);
    });
    submit?.addEventListener('click', () => submitSelection(state));
  }

  window.ProjectSymbolPicker = { open, close };
}());
