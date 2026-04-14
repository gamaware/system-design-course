'use strict';

const STEP_ARROW_MS = 300;
const STEP_PAUSE_MS = 500;
const POLL_INTERVAL_MS = 3000;
const MAX_LOG_ENTRIES = 100;

const PATTERN_DESCRIPTIONS = {
  replication:
    'Write to primary, read from replica. Observe replication lag in real time.',
  consistency:
    'Transfer enrollment between courses inside an ACID transaction. Observe commit or rollback.',
  schema:
    'Run EXPLAIN to see query plans. Add/drop indexes and compare rows scanned.',
};

const EXPLANATIONS = {
  replication: [
    {
      title: '1. INSERT on Primary',
      detail:
        'The new student row is written to the primary MySQL instance. ' +
        'The primary records the change in its binary log (binlog).',
    },
    {
      title: '2. SELECT on Replica',
      detail:
        'The replica applies binlog events via its IO and SQL threads. ' +
        'We immediately read the row from the replica to check replication.',
    },
    {
      title: '3. Check Replication Lag',
      detail:
        'SHOW REPLICA STATUS reveals Seconds_Behind_Source. ' +
        'In this local setup it is typically 0, but under heavy load it grows.',
    },
  ],
  consistency: [
    {
      title: '1. BEGIN Transaction',
      detail:
        'MySQL starts a transaction. All subsequent statements are ' +
        'isolated from other connections until COMMIT or ROLLBACK.',
    },
    {
      title: '2. DELETE + UPDATE (source course)',
      detail:
        'Remove the enrollment and decrement the enrolled count. ' +
        'If the student is not enrolled, no rows are affected.',
    },
    {
      title: '3. INSERT + UPDATE (target course)',
      detail:
        'Add the new enrollment and increment the count. ' +
        'If a unique constraint is violated, the whole transaction rolls back.',
    },
    {
      title: '4. COMMIT or ROLLBACK',
      detail:
        'On success, all changes are made permanent atomically. ' +
        'On failure, the database reverts to its state before BEGIN.',
    },
  ],
  schema: [
    {
      title: '1. EXPLAIN (Query Plan)',
      detail:
        'MySQL shows how it would execute the query. The "rows" field ' +
        'shows how many rows it expects to examine. Full scan = ~10,000.',
    },
    {
      title: '2. Add/Drop Index',
      detail:
        'A composite index on (student_id, resource) lets MySQL jump ' +
        'directly to matching rows. Rows examined drops from ~10,000 to ~20.',
    },
  ],
};

let animating = false;
let pollTimer = null;

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
}

async function apiGet(url) {
  const res = await fetch(url);
  return res.json();
}

function setButtonsDisabled(d) {
  $$('button').forEach(b => { b.disabled = d; });
}

function clearAnimations() {
  $$('.arrow').forEach(a => {
    a.classList.remove('arrow-active', 'arrow-success', 'arrow-op', 'arrow-error');
  });
  $$('.travel-dot').forEach(d => d.setAttribute('opacity', '0'));
  $$('.latency-group').forEach(g => {
    g.setAttribute('opacity', '0');
    const t = g.querySelector('.latency-label');
    if (t) t.textContent = '';
  });
  $$('.node-badge').forEach(b => b.setAttribute('opacity', '0'));
}

// --- Arrow Animation ---

async function animateArrow(arrowId, dotId, latencyId, ms, cls) {
  const arrow = $(`#${arrowId}`);
  const dot = $(`#${dotId}`);
  const latGroup = $(`#${latencyId}`);

  if (arrow) {
    arrow.classList.add('arrow-active', cls || 'arrow-op');
  }

  // Animate dot along arrow path
  if (dot && arrow) {
    const x1 = parseFloat(arrow.getAttribute('x1'));
    const y1 = parseFloat(arrow.getAttribute('y1'));
    const x2 = parseFloat(arrow.getAttribute('x2'));
    const y2 = parseFloat(arrow.getAttribute('y2'));
    dot.setAttribute('opacity', '1');
    const steps = 20;
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      dot.setAttribute('cx', x1 + (x2 - x1) * t);
      dot.setAttribute('cy', y1 + (y2 - y1) * t);
      await sleep(STEP_ARROW_MS / steps);
    }
    dot.setAttribute('opacity', '0');
  }

  // Show latency
  if (latGroup && ms !== undefined) {
    latGroup.setAttribute('opacity', '1');
    const label = latGroup.querySelector('.latency-label');
    if (label) label.textContent = `${ms.toFixed(1)}ms`;
  }
}

// --- Event Log ---

function logEvent(step) {
  const log = $('#event-log');
  const entry = document.createElement('div');
  entry.className = 'log-entry';

  const time = new Date().toLocaleTimeString('en-US', { hour12: false });
  const targetCls = step.target === 'primary' ? 'primary' : 'replica';
  const resultCls = step.result === 'OK' || step.result === 'FOUND' ||
    step.result === 'COMMITTED' ? 'ok' : 'error';

  entry.innerHTML =
    `<span class="log-time">${time}</span>` +
    `<span class="log-action">${step.action}</span>` +
    `<span class="log-target ${targetCls}">${step.target}</span>` +
    `<span class="log-result ${resultCls}">${step.result}</span>` +
    `<span class="log-latency">${step.latency_ms.toFixed(1)}ms</span>`;

  log.prepend(entry);
  while (log.children.length > MAX_LOG_ENTRIES) {
    log.removeChild(log.lastChild);
  }
}

// --- Explanation Panel ---

function showExplanation(tab) {
  const panel = $('#explanation-panel');
  const container = $('#explanation-steps');
  const items = EXPLANATIONS[tab] || [];

  if (items.length === 0) {
    panel.classList.add('hidden');
    return;
  }

  container.innerHTML = items.map((item, i) =>
    `<div class="explanation-step" id="exp-step-${i}">
      <h4>${item.title}</h4>
      <p>${item.detail}</p>
    </div>`
  ).join('');
  panel.classList.remove('hidden');
}

function highlightExpStep(index) {
  $$('.explanation-step').forEach((el, i) => {
    el.classList.toggle('active', i === index);
  });
}

// --- Result Panel ---

function showResult(status, latency, data, cls) {
  const panel = $('#result-panel');
  const statusEl = $('#result-status');
  const latencyEl = $('#result-latency');
  const dataEl = $('#result-data');

  statusEl.textContent = status;
  statusEl.className = `result-status ${cls || ''}`;
  latencyEl.textContent = `${latency.toFixed(1)}ms total`;
  dataEl.textContent = JSON.stringify(data, null, 2);
  panel.classList.remove('hidden');
}

// --- Sidebar Update ---

async function updateSidebar() {
  try {
    const state = await apiGet('/api/db/state');

    $('#stat-io').textContent = state.replica?.io_running || '--';
    $('#stat-io').className = 'stat-value ' +
      (state.replica?.io_running === 'Yes' ? 'ok' : 'warn');

    $('#stat-sql').textContent = state.replica?.sql_running || '--';
    $('#stat-sql').className = 'stat-value ' +
      (state.replica?.sql_running === 'Yes' ? 'ok' : 'warn');

    const lag = state.replica?.lag;
    $('#stat-lag').textContent = lag !== null && lag !== undefined ? lag : '--';
    $('#stat-lag').className = 'stat-value ' + (lag === 0 ? 'ok' : 'warn');

    $('#stat-primary-rows').textContent = state.primary?.students || '--';
    $('#stat-replica-rows').textContent = state.replica?.students || '--';
    $('#stat-log-rows').textContent = state.primary?.access_log_rows || '--';

    // Courses
    const courseList = $('#course-list');
    courseList.innerHTML = (state.primary?.courses || []).map(c =>
      `<li class="course-item">
        <span class="course-code">${c.code}</span>
        <span class="course-enrolled">${c.enrolled} enrolled</span>
      </li>`
    ).join('');

    // Indexes
    const indexes = state.primary?.indexes || [];
    const unique = [...new Set(indexes)];
    $('#index-list').textContent = unique.length > 0 ? unique.join(', ') : 'None';
  } catch {
    // silently retry next poll
  }
}

// --- Replication Action ---

async function doReplication() {
  if (animating) return;
  animating = true;
  setButtonsDisabled(true);
  clearAnimations();
  showExplanation('replication');

  const name = $('#repl-name').value || 'Test Student';
  const major = $('#repl-major').value;
  const email = name.toLowerCase().replace(/\s+/g, '.') +
    Math.floor(Math.random() * 9999) + '@university.edu';

  const result = await apiPost('/api/replication/write', { name, email, major });

  if (result.error) {
    showResult('ERROR', 0, result, 'rolled-back');
    animating = false;
    setButtonsDisabled(false);
    return;
  }

  for (const step of result.steps) {
    const idx = step.seq - 1;
    highlightExpStep(idx);
    logEvent(step);

    if (step.action === 'INSERT') {
      await animateArrow('arrow-app-primary', 'dot-app-primary',
        'latency-app-primary', step.latency_ms, 'arrow-op');
    } else if (step.action === 'SELECT') {
      const cls = step.result === 'FOUND' ? 'arrow-success' : 'arrow-error';
      await animateArrow('arrow-app-replica', 'dot-app-replica',
        'latency-app-replica', step.latency_ms, cls);
    }
    await sleep(STEP_PAUSE_MS);
  }

  const lastStep = result.steps[result.steps.length - 1];
  showResult(
    lastStep.data?.lag_seconds === 0 ? 'REPLICATED' : 'LAG DETECTED',
    result.total_ms,
    result.steps.map(s => ({ action: s.action, result: s.result, ms: s.latency_ms })),
    lastStep.data?.lag_seconds === 0 ? 'committed' : 'rolled-back'
  );

  await updateSidebar();
  animating = false;
  setButtonsDisabled(false);
}

// --- Consistency Action ---

async function doTransfer() {
  if (animating) return;
  animating = true;
  setButtonsDisabled(true);
  clearAnimations();
  showExplanation('consistency');

  const studentId = $('#tx-student').value;
  const fromCourse = $('#tx-from').value;
  const toCourse = $('#tx-to').value;

  const result = await apiPost('/api/consistency/transfer', {
    student_id: studentId, from_course: fromCourse, to_course: toCourse,
  });

  if (result.error) {
    showResult('ERROR', 0, result, 'rolled-back');
    animating = false;
    setButtonsDisabled(false);
    return;
  }

  let expIdx = 0;
  for (const step of result.steps) {
    logEvent(step);

    if (step.action === 'BEGIN') {
      highlightExpStep(0);
      await animateArrow('arrow-app-primary', 'dot-app-primary',
        'latency-app-primary', step.latency_ms, 'arrow-op');
    } else if (step.action.startsWith('DELETE') || step.action.startsWith('UPDATE')) {
      if (expIdx < 1) expIdx = 1;
      highlightExpStep(expIdx);
      await animateArrow('arrow-app-primary', 'dot-app-primary',
        'latency-app-primary', step.latency_ms, 'arrow-op');
    } else if (step.action.startsWith('INSERT')) {
      expIdx = 2;
      highlightExpStep(2);
      const cls = step.result === 'OK' ? 'arrow-success' : 'arrow-error';
      await animateArrow('arrow-app-primary', 'dot-app-primary',
        'latency-app-primary', step.latency_ms, cls);
    } else if (step.action === 'COMMIT' || step.action === 'ROLLBACK') {
      highlightExpStep(3);
      const cls = step.action === 'COMMIT' ? 'arrow-success' : 'arrow-error';
      await animateArrow('arrow-app-primary', 'dot-app-primary',
        'latency-app-primary', step.latency_ms, cls);
    }
    await sleep(STEP_PAUSE_MS / 2);
  }

  const committed = result.outcome === 'COMMITTED';
  showResult(
    result.outcome,
    result.total_ms,
    result.steps.map(s => ({ action: s.action, result: s.result, ms: s.latency_ms })),
    committed ? 'committed' : 'rolled-back'
  );

  await updateSidebar();
  animating = false;
  setButtonsDisabled(false);
}

// --- Schema Action ---

async function doExplain() {
  if (animating) return;
  animating = true;
  setButtonsDisabled(true);
  clearAnimations();
  showExplanation('schema');

  const studentId = $('#idx-student').value;
  const resource = $('#idx-resource').value;

  const result = await apiPost('/api/schema/explain', {
    student_id: studentId, resource,
  });

  highlightExpStep(0);
  for (const step of result.steps) {
    logEvent(step);
    await animateArrow('arrow-app-primary', 'dot-app-primary',
      'latency-app-primary', step.latency_ms, 'arrow-op');
    await sleep(STEP_PAUSE_MS);
  }

  const plan = result.steps[0]?.data || {};
  const rows = plan.rows || plan.row || '?';
  const keyUsed = plan.key || 'NONE (full scan)';

  showResult(
    `Rows scanned: ${rows} | Key: ${keyUsed}`,
    result.total_ms,
    plan,
    rows > 1000 ? 'rolled-back' : 'committed'
  );

  await updateSidebar();
  animating = false;
  setButtonsDisabled(false);
}

async function doAddIndex() {
  const result = await apiPost('/api/schema/add-index', {});
  logEvent({ action: 'CREATE INDEX', target: 'primary',
    result: result.result, latency_ms: result.latency_ms });
  await updateSidebar();
}

async function doDropIndex() {
  const result = await apiPost('/api/schema/drop-index', {});
  logEvent({ action: 'DROP INDEX', target: 'primary',
    result: result.result, latency_ms: result.latency_ms });
  await updateSidebar();
}

// --- Reset ---

async function doReset() {
  const result = await apiPost('/api/db/reset', {});
  logEvent({ action: 'RESET DB', target: 'primary',
    result: result.result || 'OK', latency_ms: 0 });
  await updateSidebar();
  $('#result-panel').classList.add('hidden');
  $('#explanation-panel').classList.add('hidden');
  clearAnimations();
}

// --- Init ---

function initTabs() {
  $$('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      $$('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const target = tab.dataset.tab;
      $$('.controls').forEach(p => {
        p.classList.toggle('active', p.id === `controls-${target}`);
      });
      const desc = $('#pattern-description');
      if (desc && PATTERN_DESCRIPTIONS[target]) {
        desc.textContent = PATTERN_DESCRIPTIONS[target];
      }
      showExplanation(target);
      clearAnimations();
      $('#result-panel').classList.add('hidden');
    });
  });
}

// --- SQL Console ---

let consoleHistory = [];
let consoleHistoryIndex = -1;

async function doSqlExec() {
  const input = $('#console-input');
  const query = input.value.trim();
  if (!query) return;

  const target = document.querySelector('.target-btn.active')?.dataset.target || 'primary';
  const output = $('#console-output');

  // Add to history
  consoleHistory.unshift(query);
  consoleHistoryIndex = -1;

  // Show query
  const queryDiv = document.createElement('div');
  queryDiv.className = 'console-query';
  queryDiv.textContent = `mysql(${target})> ${query}`;
  output.appendChild(queryDiv);

  const result = await apiPost('/api/sql/exec', { query, target });

  if (result.error) {
    const errDiv = document.createElement('div');
    errDiv.className = 'console-error';
    errDiv.textContent = `ERROR: ${result.error}`;
    output.appendChild(errDiv);
  } else if (result.columns) {
    // Build HTML table
    const table = document.createElement('table');
    table.className = 'console-result-table';
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    result.columns.forEach(col => {
      const th = document.createElement('th');
      th.textContent = col;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    const maxRows = Math.min(result.rows.length, 20);
    for (let i = 0; i < maxRows; i++) {
      const tr = document.createElement('tr');
      result.columns.forEach(col => {
        const td = document.createElement('td');
        td.textContent = result.rows[i][col] ?? 'NULL';
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    output.appendChild(table);

    const meta = document.createElement('div');
    meta.className = 'console-meta';
    const truncated = result.rows.length > 20 ? ` (showing 20 of ${result.rows.length})` : '';
    meta.textContent =
      `${result.row_count} row(s)${truncated} in ${result.latency_ms}ms`;
    output.appendChild(meta);
  } else {
    const metaDiv = document.createElement('div');
    metaDiv.className = 'console-meta';
    metaDiv.textContent =
      `${result.affected_rows} row(s) affected in ${result.latency_ms}ms`;
    output.appendChild(metaDiv);
  }

  // Log it
  logEvent({
    action: query.split(' ').slice(0, 2).join(' '),
    target,
    result: result.error ? 'ERROR' : 'OK',
    latency_ms: result.latency_ms || 0,
  });

  output.scrollTop = output.scrollHeight;
  input.value = '';
  await updateSidebar();
}

function initConsole() {
  $('#console-submit').addEventListener('click', doSqlExec);
  $('#console-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      doSqlExec();
    } else if (e.key === 'ArrowUp' && consoleHistory.length > 0) {
      consoleHistoryIndex = Math.min(
        consoleHistoryIndex + 1, consoleHistory.length - 1
      );
      $('#console-input').value = consoleHistory[consoleHistoryIndex];
    } else if (e.key === 'ArrowDown') {
      consoleHistoryIndex = Math.max(consoleHistoryIndex - 1, -1);
      $('#console-input').value =
        consoleHistoryIndex >= 0 ? consoleHistory[consoleHistoryIndex] : '';
    }
  });

  // Target toggle buttons
  $$('.target-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.target-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const target = btn.dataset.target;
      const prompt = $('.console-prompt');
      if (prompt) {
        prompt.textContent = target === 'replica' ? 'replica>' : 'mysql>';
      }
    });
  });

  // Clear button
  $('#console-clear').addEventListener('click', () => {
    $('#console-output').innerHTML = '';
  });
}

function initButtons() {
  $('#repl-write').addEventListener('click', doReplication);
  $('#tx-transfer').addEventListener('click', doTransfer);
  $('#idx-explain').addEventListener('click', doExplain);
  $('#idx-add').addEventListener('click', doAddIndex);
  $('#idx-drop').addEventListener('click', doDropIndex);
  $('#btn-reset-db').addEventListener('click', doReset);
}

function startPolling() {
  updateSidebar();
  pollTimer = setInterval(updateSidebar, POLL_INTERVAL_MS);
}

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initButtons();
  initConsole();
  startPolling();
  showExplanation('replication');
});
