(function () {
  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
  }

  function shortText(value, len = 150) {
    const text = String(value || '').replace(/\s+/g, ' ').trim();
    return text.length > len ? `${text.slice(0, len)}…` : text;
  }

  function badge(text, kind = '') {
    return `<span class="schema-badge ${kind}">${escapeHtml(text || '—')}</span>`;
  }

  function requirementBadge(requirementId) {
    const id = String(requirementId || '');
    return `<span class="schema-badge req schema-requirement-link" data-schema-action="open-requirement" data-requirement-id="${escapeHtml(id)}" title="Открыть требование ${escapeHtml(id)}">${escapeHtml(id || '—')}</span>`;
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
    return `<span class="schema-kind ${escapeHtml(normalized)}" title="${escapeHtml(kindTitle(normalized))}" aria-label="${escapeHtml(kindTitle(normalized))}">${escapeHtml(kindIcon(normalized))}</span>`;
  }

  function render(container, model) {
    if (!container) return;
    if (!model) {
      container.innerHTML = '<div class="empty-state">Схема проекта ещё не загружена.</div>';
      return;
    }
    const nodes = Array.isArray(model.nodes) ? model.nodes : [];
    const requirements = Array.isArray(model.requirements) ? model.requirements : [];
    const links = Array.isArray(model.links) ? model.links : [];
    const children = buildChildren(nodes);
    const nodeById = Object.fromEntries(nodes.map(node => [node.id, node]));
    const requirementById = Object.fromEntries(requirements.map(item => [item.id, item]));
    const linksByRequirement = groupLinksByRequirement(links);
    const roots = (children.get(null) || []).concat(children.get('') || []);
    const linkedRequirementIds = new Set(links.map(link => link.requirement_id));
    const orphanLinks = links.filter(link => !nodeById[link.target_id]);

    container.innerHTML = `
      <div class="project-schema-meta">
        <span>${badge(`${nodes.length} узлов`, 'blue')}</span>
        <span>${badge(`${links.length} связей`, links.length ? 'ok' : '')}</span>
        <span>${badge(`${linkedRequirementIds.size} требований`, linkedRequirementIds.size ? 'ok' : '')}</span>
        <span class="schema-path">knowledge: ${escapeHtml(model.knowledge_path || '—')}</span>
      </div>
      ${orphanLinks.length ? `<div class="message warn-message">Есть связи с отсутствующими узлами: ${orphanLinks.length}</div>` : ''}
      <div class="project-schema-layout" data-schema-split>
        <section class="project-schema-tree-panel">
          <div class="schema-column-title">Структура проекта</div>
          <div class="project-schema-tree">
            ${roots.length ? roots.map(node => renderNode(node, children, 0)).join('') : '<div class="empty-state">В knowledge.yaml нет модулей или символов.</div>'}
          </div>
        </section>
        <div class="project-schema-resizer" role="separator" aria-label="Изменить ширину структуры проекта" aria-orientation="vertical" title="Потяните, чтобы изменить ширину структуры проекта"></div>
        <section class="project-schema-req-panel">
          <div class="schema-column-title">Требования и связанные элементы</div>
          <div class="project-schema-requirements">
            ${requirements.length ? requirements.map(req => renderRequirement(req, linksByRequirement.get(req.id) || [], nodeById)).join('') : '<div class="empty-state">Файл требований пуст.</div>'}
            ${renderMissingRequirements(linkedRequirementIds, requirementById, linksByRequirement, nodeById)}
          </div>
        </section>
      </div>
    `;
    attachSchemaSplitter(container);
    attachRequirementBadgeLinks(container);
  }

  function attachRequirementBadgeLinks(container) {
    container.querySelectorAll('[data-schema-action="open-requirement"][data-requirement-id]').forEach(element => {
      element.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        const requirementId = element.dataset.requirementId;
        if (!requirementId) return;
        window.dispatchEvent(new CustomEvent('project-schema:open-requirement', {
          detail: { requirementId }
        }));
      });
    });
  }

  const SCHEMA_SPLITTER_STORAGE_KEY = 'codeui.projectSchema.treeWidth';

  function attachSchemaSplitter(container) {
    const layout = container.querySelector('[data-schema-split]');
    const resizer = layout ? layout.querySelector('.project-schema-resizer') : null;
    if (!layout || !resizer) return;

    const storedWidth = readStoredSchemaTreeWidth();
    if (storedWidth) {
      layout.style.setProperty('--project-schema-tree-width', `${storedWidth}px`);
    }

    resizer.addEventListener('pointerdown', event => {
      event.preventDefault();
      resizer.setPointerCapture(event.pointerId);
      layout.classList.add('is-resizing');
      document.body.classList.add('project-schema-resizing');

      const handleMove = moveEvent => {
        const bounds = layout.getBoundingClientRect();
        const width = clampSchemaTreeWidth(moveEvent.clientX - bounds.left, bounds.width);
        layout.style.setProperty('--project-schema-tree-width', `${width}px`);
        storeSchemaTreeWidth(width);
      };

      const handleUp = upEvent => {
        if (resizer.hasPointerCapture(upEvent.pointerId)) {
          resizer.releasePointerCapture(upEvent.pointerId);
        }
        layout.classList.remove('is-resizing');
        document.body.classList.remove('project-schema-resizing');
        resizer.removeEventListener('pointermove', handleMove);
        resizer.removeEventListener('pointerup', handleUp);
        resizer.removeEventListener('pointercancel', handleUp);
      };

      resizer.addEventListener('pointermove', handleMove);
      resizer.addEventListener('pointerup', handleUp);
      resizer.addEventListener('pointercancel', handleUp);
    });
  }

  function clampSchemaTreeWidth(width, layoutWidth) {
    const minWidth = 300;
    const maxWidth = Math.max(minWidth, Math.min(layoutWidth - 360, 760));
    return Math.round(Math.min(Math.max(width, minWidth), maxWidth));
  }

  function readStoredSchemaTreeWidth() {
    try {
      const value = Number(window.localStorage.getItem(SCHEMA_SPLITTER_STORAGE_KEY));
      return Number.isFinite(value) && value > 0 ? value : null;
    } catch (_error) {
      return null;
    }
  }

  function storeSchemaTreeWidth(width) {
    try {
      window.localStorage.setItem(SCHEMA_SPLITTER_STORAGE_KEY, String(width));
    } catch (_error) {
      // localStorage can be unavailable in restricted browser modes.
    }
  }

  function renderGraph(container, model) {
    if (!container) return;
    if (!model) {
      container.innerHTML = '<div class="empty-state">Карта связей ещё не загружена.</div>';
      return;
    }
    const nodes = Array.isArray(model.nodes) ? model.nodes : [];
    const requirements = Array.isArray(model.requirements) ? model.requirements : [];
    const links = Array.isArray(model.links) ? model.links : [];
    const children = buildChildren(nodes);
    const nodeById = Object.fromEntries(nodes.map(node => [node.id, node]));
    const requirementById = Object.fromEntries(requirements.map(item => [item.id, item]));
    const usableLinks = links.filter(link => nodeById[link.target_id]);
    const roots = (children.get(null) || []).concat(children.get('') || []);
    const treeRows = buildGraphTreeRows(roots, children, nodes);
    const treeYById = new Map(treeRows.map(row => [row.node.id, graphTreeRowY(row.index)]));
    const requirementRows = buildGraphRequirementRows(requirements, usableLinks, treeYById);
    const requirementYById = new Map(requirementRows.map(row => [row.item.id, graphRequirementRowY(row.index)]));
    const missingRequirementRows = buildMissingGraphRequirementRows(usableLinks, requirementById, requirementRows.length, treeYById);
    const allRequirementRows = requirementRows.concat(missingRequirementRows);
    for (const row of missingRequirementRows) {
      requirementYById.set(row.item.id, graphRequirementRowY(row.index));
    }
    const graphWidth = 1480;
    const graphHeight = Math.max(
      allRequirementRows.length * GRAPH_REQ_ROW_HEIGHT + GRAPH_MARGIN * 2,
      treeRows.length * GRAPH_TREE_ROW_HEIGHT + GRAPH_MARGIN * 2,
      360
    );
    const linkedTargetIds = new Set(usableLinks.map(link => link.target_id));
    const linkedRequirementIds = new Set(usableLinks.map(link => link.requirement_id));
    const linkPaths = usableLinks
      .filter(link => requirementYById.has(link.requirement_id) && treeYById.has(link.target_id))
      .map(link => renderGraphLink(link, requirementYById.get(link.requirement_id), treeYById.get(link.target_id)));

    container.innerHTML = `
      <div class="project-schema-meta">
        <span>${badge(`${usableLinks.length} связей`, usableLinks.length ? 'ok' : '')}</span>
        <span>${badge(`${linkedRequirementIds.size} связанных требований`, linkedRequirementIds.size ? 'ok' : '')}</span>
        <span>${badge(`${linkedTargetIds.size} связанных элементов`, linkedTargetIds.size ? 'blue' : '')}</span>
        <span>${badge(`${treeRows.length} узлов структуры`, treeRows.length ? 'blue' : '')}</span>
      </div>
      ${usableLinks.length ? '' : '<div class="message warn-message">В knowledge.yaml пока нет связей с требованиями; показаны все требования и структура проекта без линий.</div>'}
      <div class="schema-graph-scroll">
        <svg class="schema-graph-svg" viewBox="0 0 ${graphWidth} ${graphHeight}" width="${graphWidth}" height="${graphHeight}" preserveAspectRatio="xMinYMin meet" role="img" aria-label="Карта связей требований и структуры проекта">
          <defs>
            <marker id="schema-graph-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" class="schema-graph-arrow" />
            </marker>
          </defs>
          <text class="schema-graph-title" x="${GRAPH_REQ_X}" y="22">Требования</text>
          <text class="schema-graph-title" x="${GRAPH_TREE_X}" y="22">Структура проекта</text>
          <g class="schema-graph-links">${linkPaths.join('')}</g>
          <g class="schema-graph-requirements">${allRequirementRows.map(row => renderGraphRequirementNode(row, linkedRequirementIds)).join('')}</g>
          <g class="schema-graph-project-tree">${renderGraphTreeGuides(treeRows)}${treeRows.map(row => renderGraphProjectNode(row, linkedTargetIds)).join('')}</g>
        </svg>
      </div>
    `;
    attachGraphSelection(container);
  }

  const GRAPH_MARGIN = 42;
  const GRAPH_REQ_X = 12;
  const GRAPH_REQ_WIDTH = 310;
  const GRAPH_REQ_ROW_HEIGHT = 82;
  const GRAPH_TREE_X = 470;
  const GRAPH_TREE_WIDTH = 980;
  const GRAPH_TREE_ROW_HEIGHT = 32;
  const GRAPH_TREE_INDENT = 26;

  function graphRequirementRowY(index) {
    return GRAPH_MARGIN + index * GRAPH_REQ_ROW_HEIGHT;
  }

  function graphTreeRowY(index) {
    return GRAPH_MARGIN + index * GRAPH_TREE_ROW_HEIGHT;
  }

  function buildGraphTreeRows(roots, children, nodes) {
    const rows = [];
    const rendered = new Set();
    const visit = (node, level) => {
      rows.push({ node, level, index: rows.length });
      rendered.add(node.id);
      for (const child of children.get(node.id) || []) {
        visit(child, level + 1);
      }
    };
    for (const root of roots) {
      visit(root, 0);
    }
    for (const node of nodes) {
      if (!rendered.has(node.id)) {
        rows.push({ node, level: 0, index: rows.length });
      }
    }
    rows.forEach((row, index) => { row.index = index; });
    return rows;
  }

  function buildGraphRequirementRows(requirements, links, treeYById) {
    const averages = new Map();
    for (const req of requirements) {
      const ys = links
        .filter(link => link.requirement_id === req.id && treeYById.has(link.target_id))
        .map(link => treeYById.get(link.target_id));
      if (ys.length) {
        averages.set(req.id, ys.reduce((acc, value) => acc + value, 0) / ys.length);
      }
    }
    return [...requirements]
      .sort((a, b) => compareGraphRequirementOrder(a, b, averages))
      .map((item, index) => ({ item, index, missing: false }));
  }

  function buildMissingGraphRequirementRows(links, requirementById, startIndex, treeYById) {
    const ids = [...new Set(links.map(link => link.requirement_id))]
      .filter(id => !requirementById[id])
      .sort();
    return ids.map((id, offset) => ({
      item: { id, type: '', status: '', description: 'Требование отсутствует в requirements.json' },
      index: startIndex + offset,
      missing: true,
      averageY: averageLinkedTargetY(id, links, treeYById),
    }));
  }

  function averageLinkedTargetY(requirementId, links, treeYById) {
    const ys = links
      .filter(link => link.requirement_id === requirementId && treeYById.has(link.target_id))
      .map(link => treeYById.get(link.target_id));
    return ys.length ? ys.reduce((acc, value) => acc + value, 0) / ys.length : Number.MAX_SAFE_INTEGER;
  }

  function compareGraphRequirementOrder(a, b, averages) {
    const aLinked = averages.has(a.id);
    const bLinked = averages.has(b.id);
    if (aLinked && bLinked) {
      const diff = averages.get(a.id) - averages.get(b.id);
      if (Math.abs(diff) > 0.01) return diff;
    }
    if (aLinked !== bLinked) return aLinked ? -1 : 1;
    return String(a.id).localeCompare(String(b.id));
  }

  function renderGraphLink(link, reqY, treeY) {
    const x1 = GRAPH_REQ_X + GRAPH_REQ_WIDTH;
    const y1 = reqY + 31;
    const x2 = GRAPH_TREE_X - 10;
    const y2 = treeY + 14;
    const c1 = x1 + 80;
    const c2 = x2 - 95;
    return `<path class="schema-graph-link" data-requirement-id="${escapeSvg(link.requirement_id)}" data-target-id="${escapeSvg(link.target_id)}" d="M ${x1} ${y1} C ${c1} ${y1}, ${c2} ${y2}, ${x2} ${y2}" marker-end="url(#schema-graph-arrow)" />`;
  }

  function renderGraphRequirementNode(row, linkedRequirementIds) {
    const req = row.item;
    const y = graphRequirementRowY(row.index);
    const isLinked = linkedRequirementIds.has(req.id);
    return `
      <g class="schema-graph-req-node ${isLinked ? 'is-linked' : 'is-unlinked'}" data-requirement-id="${escapeSvg(req.id)}" transform="translate(${GRAPH_REQ_X}, ${y})">
        <title>${escapeSvg(req.id)}</title>
        <rect width="${GRAPH_REQ_WIDTH}" height="62" rx="8" />
        <text class="schema-graph-req-id" data-graph-action="open-requirement" x="12" y="20">${escapeSvg(req.id)}</text>
        ${req.type ? `<text class="schema-graph-req-type" x="118" y="20">${escapeSvg(req.type)}</text>` : ''}
        <foreignObject x="12" y="28" width="${GRAPH_REQ_WIDTH - 24}" height="28">
          <div xmlns="http://www.w3.org/1999/xhtml" class="schema-graph-node-text">${escapeHtml(shortText(req.description || req.title, 92))}</div>
        </foreignObject>
      </g>
    `;
  }

  function renderGraphProjectNode(row, linkedTargetIds) {
    const node = row.node;
    const y = graphTreeRowY(row.index);
    const indent = Math.min(row.level, 12) * GRAPH_TREE_INDENT;
    const rowX = GRAPH_TREE_X + indent;
    const rowWidth = Math.max(260, GRAPH_TREE_WIDTH - indent);
    const isLinked = linkedTargetIds.has(node.id);
    return `
      <g class="schema-graph-project-node ${isLinked ? 'is-linked' : 'is-unlinked'} ${escapeHtml(node.kind || 'symbol')}" data-node-id="${escapeSvg(node.id)}" transform="translate(${rowX}, ${y})">
        <title>${escapeSvg(node.id)}</title>
        <rect width="${rowWidth}" height="25" rx="6" />
        <text class="schema-graph-kind" x="9" y="17">${escapeSvg(kindIcon(node.kind))}</text>
        <text class="schema-graph-node-label" x="34" y="17">${escapeSvg(shortText(node.label || node.id, 64))}</text>
      </g>
    `;
  }

  function renderGraphTreeGuides(treeRows) {
    return treeRows
      .filter(row => row.level > 0)
      .map(row => {
        const y = graphTreeRowY(row.index) + 12.5;
        const x1 = GRAPH_TREE_X + (Math.min(row.level, 12) - 1) * GRAPH_TREE_INDENT + 14;
        const x2 = GRAPH_TREE_X + Math.min(row.level, 12) * GRAPH_TREE_INDENT - 4;
        return `<path class="schema-graph-tree-guide" d="M ${x1} ${y} L ${x2} ${y}" />`;
      })
      .join('');
  }

  function attachGraphSelection(container) {
    const graph = container.querySelector('.schema-graph-svg');
    if (!graph) return;
    const requirementNodes = [...graph.querySelectorAll('.schema-graph-req-node')];
    const links = [...graph.querySelectorAll('.schema-graph-link')];
    const projectNodes = [...graph.querySelectorAll('.schema-graph-project-node')];

    function clearSelection() {
      graph.classList.remove('has-selected-requirement', 'has-selected-project-node');
      requirementNodes.forEach(node => node.classList.remove('is-selected', 'is-highlighted'));
      links.forEach(link => link.classList.remove('is-highlighted'));
      projectNodes.forEach(node => node.classList.remove('is-selected', 'is-highlighted'));
    }

    function emitRequirementOpen(requirementId) {
      const id = String(requirementId || '');
      if (!id) return;
      window.dispatchEvent(new CustomEvent('project-schema:open-requirement', {
        detail: { requirementId: id },
      }));
    }

    function selectRequirement(requirementId) {
      const selectedRequirement = String(requirementId || '');
      const targetIds = new Set(
        links
          .filter(link => link.dataset.requirementId === selectedRequirement)
          .map(link => link.dataset.targetId)
      );
      clearSelection();
      graph.classList.add('has-selected-requirement');
      requirementNodes.forEach(node => {
        node.classList.toggle('is-selected', node.dataset.requirementId === selectedRequirement);
      });
      links.forEach(link => {
        link.classList.toggle('is-highlighted', link.dataset.requirementId === selectedRequirement);
      });
      projectNodes.forEach(node => {
        node.classList.toggle('is-highlighted', targetIds.has(node.dataset.nodeId));
      });
    }

    function selectProjectNode(nodeId) {
      const selectedNodeId = String(nodeId || '');
      const requirementIds = new Set(
        links
          .filter(link => link.dataset.targetId === selectedNodeId)
          .map(link => link.dataset.requirementId)
      );
      clearSelection();
      graph.classList.add('has-selected-project-node');
      projectNodes.forEach(node => {
        node.classList.toggle('is-selected', node.dataset.nodeId === selectedNodeId);
      });
      links.forEach(link => {
        link.classList.toggle('is-highlighted', link.dataset.targetId === selectedNodeId);
      });
      requirementNodes.forEach(node => {
        node.classList.toggle('is-highlighted', requirementIds.has(node.dataset.requirementId));
      });
    }

    requirementNodes.forEach(node => {
      node.addEventListener('click', event => {
        event.stopPropagation();
        const requirementId = node.dataset.requirementId;
        const actionTarget = event.target.closest ? event.target.closest('[data-graph-action="open-requirement"]') : null;
        if (actionTarget) {
          emitRequirementOpen(requirementId);
          return;
        }
        if (node.classList.contains('is-selected')) {
          clearSelection();
        } else {
          selectRequirement(requirementId);
        }
      });
    });
    projectNodes.forEach(node => {
      node.addEventListener('click', event => {
        event.stopPropagation();
        const nodeId = node.dataset.nodeId;
        if (node.classList.contains('is-selected')) {
          clearSelection();
        } else {
          selectProjectNode(nodeId);
        }
      });
    });
    graph.addEventListener('click', clearSelection);
  }

  function escapeSvg(value) {
    return escapeHtml(value).replace(/'/g, '&#39;');
  }

  function sortRequirementIds(ids, requirements) {
    const order = new Map(requirements.map((item, index) => [item.id, index]));
    return [...ids].sort((a, b) => {
      const ai = order.has(a) ? order.get(a) : Number.MAX_SAFE_INTEGER;
      const bi = order.has(b) ? order.get(b) : Number.MAX_SAFE_INTEGER;
      if (ai !== bi) return ai - bi;
      return String(a).localeCompare(String(b));
    });
  }

  function buildVisibleNodeIds(directLinkedNodeIds, nodeById) {
    const result = new Set();
    for (const nodeId of directLinkedNodeIds) {
      let current = nodeById[nodeId];
      while (current && !result.has(current.id)) {
        result.add(current.id);
        current = current.parent_id ? nodeById[current.parent_id] : null;
      }
    }
    return result;
  }

  function buildVisibleTreeRows(nodes, children, visibleNodeIds) {
    const roots = (children.get(null) || []).concat(children.get('') || []);
    const rows = [];
    const visit = (node, level) => {
      if (!visibleNodeIds.has(node.id)) return;
      rows.push({ node, level, index: rows.length });
      for (const child of children.get(node.id) || []) {
        visit(child, level + 1);
      }
    };
    for (const root of roots) {
      visit(root, 0);
    }
    const rendered = new Set(rows.map(row => row.node.id));
    for (const node of nodes) {
      if (visibleNodeIds.has(node.id) && !rendered.has(node.id)) {
        rows.push({ node, level: 0, index: rows.length });
      }
    }
    rows.forEach((row, index) => { row.index = index; });
    return rows;
  }

  function renderTraceMapLine(reqRow, treeRow, reqRowHeight, treeRowHeight) {
    const y1 = reqRow * reqRowHeight + 32;
    const y2 = treeRow * treeRowHeight + 18;
    return `<path class="trace-map-link-line" d="M 320 ${y1} C 450 ${y1}, 555 ${y2}, 690 ${y2}" />`;
  }

  function renderTraceMapRequirement(row, rowHeight) {
    const req = row.item;
    return `
      <article class="trace-map-req-card" style="top:${row.index * rowHeight}px">
        <div class="schema-req-head">
          <span class="schema-req-id">${escapeHtml(req.id)}</span>
          ${req.type ? badge(req.type, 'blue') : ''}
        </div>
        <div class="trace-map-req-text">${escapeHtml(shortText(req.description || req.title, 92))}</div>
      </article>
    `;
  }

  function renderTraceMapNode(row, rowHeight, directLinkedNodeIds) {
    const node = row.node;
    const isLinked = directLinkedNodeIds.has(node.id);
    const indent = Math.min(row.level, 10) * 17;
    const requirements = Array.isArray(node.requirement_ids) ? node.requirement_ids : [];
    return `
      <div class="trace-map-tree-row ${isLinked ? 'is-linked' : 'is-ancestor'}" style="top:${row.index * rowHeight}px; padding-left:${indent}px">
        <span class="trace-map-tree-stem" aria-hidden="true"></span>
        ${kindBadge(node.kind)}
        <span class="trace-map-node-label" title="${escapeHtml(node.id)}">${escapeHtml(node.label || node.id)}</span>
        ${requirements.map(req => badge(req, 'req')).join('')}
        <span class="trace-map-node-path" title="${escapeHtml(node.id)}">${escapeHtml(node.id)}</span>
      </div>
    `;
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

  function compareNodes(a, b) {
    const ak = kindRank(a.kind);
    const bk = kindRank(b.kind);
    if (ak !== bk) return ak - bk;
    return String(a.id).localeCompare(String(b.id));
  }

  function compareIdsByDepth(a, b) {
    const da = String(a).split('.').length;
    const db = String(b).split('.').length;
    if (da !== db) return da - db;
    return String(a).localeCompare(String(b));
  }

  function kindRank(kind) {
    if (kind === 'package') return 0;
    if (kind === 'module') return 1;
    if (kind === 'class') return 2;
    if (kind === 'member') return 3;
    return 4;
  }

  function renderNode(node, children, level) {
    const childNodes = children.get(node.id) || [];
    const requirements = Array.isArray(node.requirement_ids) ? node.requirement_ids : [];
    return `
      <div class="schema-node schema-level-${Math.min(level, 8)} ${requirements.length ? 'has-links' : ''}">
        <div class="schema-node-line">
          ${kindBadge(node.kind)}
          <span class="schema-node-title" title="${escapeHtml(node.id)}">${escapeHtml(node.label || node.id)}</span>
          ${requirements.map(req => requirementBadge(req)).join('')}
        </div>
        ${node.title && node.title !== node.label ? `<div class="schema-node-subtitle">${escapeHtml(shortText(node.title, 120))}</div>` : ''}
      </div>
      ${childNodes.map(child => renderNode(child, children, level + 1)).join('')}
    `;
  }

  function groupLinksByRequirement(links) {
    const result = new Map();
    for (const link of links) {
      if (!result.has(link.requirement_id)) result.set(link.requirement_id, []);
      result.get(link.requirement_id).push(link);
    }
    for (const [key, value] of result.entries()) {
      result.set(key, value.sort((a, b) => String(a.target_id).localeCompare(String(b.target_id))));
    }
    return result;
  }

  function renderRequirement(req, links, nodeById) {
    const linkedNodes = links.map(link => nodeById[link.target_id]).filter(Boolean);
    const hasLinks = linkedNodes.length > 0;
    return `
      <article class="schema-req-card ${hasLinks ? 'has-links' : ''}">
        <div class="schema-req-head">
          <span class="schema-req-id">${escapeHtml(req.id)}</span>
          ${req.type ? badge(req.type, 'blue') : ''}
          ${req.status ? badge(req.status) : ''}
          <span class="schema-link-count">${linkedNodes.length}</span>
        </div>
        <div class="schema-req-text">${escapeHtml(shortText(req.description || req.title, 210))}</div>
        ${hasLinks ? `<ul class="schema-linked-list">${linkedNodes.map(node => `<li>${kindBadge(node.kind)} ${escapeHtml(node.id)}</li>`).join('')}</ul>` : '<div class="schema-no-links">Связей нет</div>'}
      </article>
    `;
  }

  function renderMissingRequirements(linkedRequirementIds, requirementById, linksByRequirement, nodeById) {
    const missing = [...linkedRequirementIds].filter(id => !requirementById[id]).sort();
    if (!missing.length) return '';
    return `
      <details class="schema-missing-reqs">
        <summary>Связи с требованиями, которых нет в requirements.json: ${missing.length}</summary>
        ${missing.map(id => renderRequirement({ id, title: id, description: '' }, linksByRequirement.get(id) || [], nodeById)).join('')}
      </details>
    `;
  }

  window.ProjectSchemaView = { render, renderGraph };
}());
