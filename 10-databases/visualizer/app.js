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
  cap:
    'Stop replication to simulate a network partition. Write data and observe divergence between primary and replica.',
  views:
    'Compare expensive multi-table JOINs vs a pre-computed materialized view. See the read-speed vs write-cost trade-off.',
  vertical:
    'Adjust the InnoDB buffer pool size and benchmark query performance. More RAM = more data cached in memory = faster reads.',
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
  cap: [
    {
      title: '1. Stop Replication (Simulate Partition)',
      detail:
        'STOP REPLICA halts the IO and SQL threads on the replica. ' +
        'New writes to the primary will NOT propagate. This simulates a network partition.',
    },
    {
      title: '2. Write & Compare',
      detail:
        'INSERT a row on the primary, then immediately read from both nodes. ' +
        'Primary has the data (consistent). Replica does NOT (stale). This is the CAP trade-off.',
    },
    {
      title: '3. Start Replication (Recovery)',
      detail:
        'START REPLICA resumes the threads. The replica catches up by replaying ' +
        'missed binlog events. Data becomes consistent again across both nodes.',
    },
  ],
  views: [
    {
      title: '1. Query with JOINs (Expensive)',
      detail:
        'A 3-table JOIN (students + enrollments + courses) scans multiple tables ' +
        'and computes the result on every query. Slow at scale.',
    },
    {
      title: '2. Materialized View (Pre-computed)',
      detail:
        'CREATE TABLE ... AS SELECT pre-computes the JOIN result into a single flat table. ' +
        'Reads are fast (single table scan), but the view becomes stale after writes.',
    },
    {
      title: '3. Refresh (The Trade-off)',
      detail:
        'After new data is inserted, the materialized view must be refreshed (dropped and recreated). ' +
        'This is the read-speed vs data-freshness trade-off.',
    },
  ],
  vertical: [
    {
      title: '1. Set Buffer Pool Size',
      detail:
        'innodb_buffer_pool_size controls how much RAM MySQL uses to cache data pages. ' +
        'More RAM = more data stays in memory instead of being read from disk.',
    },
    {
      title: '2. Run Benchmark',
      detail:
        '200 random queries hit the access_log table. With a small buffer, most reads go to disk (slow). ' +
        'With a large buffer, the working set fits in RAM (fast).',
    },
    {
      title: '3. Compare Results',
      detail:
        'The buffer hit ratio shows what percentage of reads were served from memory. ' +
        'Higher ratio = faster queries. This is vertical scaling: bigger machine, more RAM.',
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

// --- SQL Glass Box (auto-log queries to console) ---

function logSqlToConsole(result) {
  const output = $('#console-output');
  const steps = result.steps || [];

  steps.forEach(step => {
    if (!step.sql) return;
    const qDiv = document.createElement('div');
    qDiv.className = 'console-query';
    qDiv.textContent = `mysql(${step.target})> ${step.sql}`;
    output.appendChild(qDiv);

    const rDiv = document.createElement('div');
    rDiv.className = step.result.toLowerCase().includes('error') ||
      step.result.toLowerCase().includes('not found') ||
      step.result.toLowerCase().includes('stale')
      ? 'console-error' : 'console-meta';
    rDiv.textContent = `-- ${step.result} (${step.latency_ms}ms)`;
    output.appendChild(rDiv);
  });

  output.scrollTop = output.scrollHeight;
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

function showResult(status, latency, data, cls, apiResult) {
  const panel = $('#result-panel');
  const statusEl = $('#result-status');
  const latencyEl = $('#result-latency');
  const dataEl = $('#result-data');

  statusEl.textContent = status;
  statusEl.className = `result-status ${cls || ''}`;
  latencyEl.textContent = `${latency.toFixed(1)}ms total`;
  dataEl.textContent = JSON.stringify(data, null, 2);
  panel.classList.remove('hidden');

  // Show interpretation below the JSON
  const existingInterp = panel.querySelector('.result-interpretation');
  if (existingInterp) existingInterp.remove();
  if (apiResult?.interpretation) {
    const iDiv = document.createElement('div');
    iDiv.className = 'result-interpretation';
    iDiv.textContent = apiResult.interpretation;
    panel.appendChild(iDiv);
  }

  // Log SQL queries to the console (without interpretation)
  if (apiResult) {
    logSqlToConsole(apiResult);
  }
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
    lastStep.data?.lag_seconds === 0 ? 'committed' : 'rolled-back',
    result
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
    committed ? 'committed' : 'rolled-back',
    result
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
    rows > 1000 ? 'rolled-back' : 'committed',
    result
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

// --- CAP Theorem Actions ---

async function doCapStop() {
  const result = await apiPost('/api/cap/stop-replication', {});
  logEvent({ action: 'STOP REPLICA', target: 'replica',
    result: result.result, latency_ms: result.latency_ms });
  showExplanation('cap');
  highlightExpStep(0);
  // Visual: grey out replica node
  const replicaRect = document.querySelector('#node-replica rect');
  if (replicaRect) replicaRect.style.opacity = '0.4';
  showResult('PARTITION ACTIVE', result.latency_ms,
    { message: 'Replication stopped. Replica will not receive new writes.' },
    'rolled-back', result);
  await updateSidebar();
}

async function doCapStart() {
  const result = await apiPost('/api/cap/start-replication', {});
  logEvent({ action: 'START REPLICA', target: 'replica',
    result: result.result, latency_ms: result.latency_ms });
  showExplanation('cap');
  highlightExpStep(2);
  // Visual: restore replica node
  const replicaRect = document.querySelector('#node-replica rect');
  if (replicaRect) replicaRect.style.opacity = '1';
  showResult('PARTITION RECOVERED', result.latency_ms,
    { message: 'Replication resumed. Replica is catching up.' },
    'committed', result);
  await updateSidebar();
}

async function doCapTest() {
  if (animating) return;
  animating = true;
  setButtonsDisabled(true);
  clearAnimations();
  showExplanation('cap');

  const result = await apiPost('/api/cap/test-divergence', {
    name: 'CAP Student ' + Math.floor(Math.random() * 1000),
  });

  if (result.error) {
    showResult('ERROR', 0, result, 'rolled-back');
    animating = false;
    setButtonsDisabled(false);
    return;
  }

  for (const step of result.steps) {
    logEvent(step);
    if (step.action === 'INSERT') {
      highlightExpStep(0);
      await animateArrow('arrow-app-primary', 'dot-app-primary',
        'latency-app-primary', step.latency_ms, 'arrow-op');
    } else if (step.action === 'SELECT (primary)') {
      highlightExpStep(1);
      await animateArrow('arrow-app-primary', 'dot-app-primary',
        'latency-app-primary', step.latency_ms, 'arrow-success');
    } else if (step.action === 'SELECT (replica)') {
      highlightExpStep(1);
      const cls = step.result.includes('stale') ? 'arrow-error' : 'arrow-success';
      await animateArrow('arrow-app-replica', 'dot-app-replica',
        'latency-app-replica', step.latency_ms, cls);
    }
    await sleep(STEP_PAUSE_MS);
  }

  const diverged = result.outcome.includes('DIVERGED');
  showResult(
    result.outcome,
    result.total_ms,
    result.steps.map(s => ({ action: s.action, result: s.result, ms: s.latency_ms })),
    diverged ? 'rolled-back' : 'committed',
    result
  );

  await updateSidebar();
  animating = false;
  setButtonsDisabled(false);
}

// --- Materialized Views Actions ---

async function doViewsCreate() {
  const result = await apiPost('/api/views/create', {});
  logEvent({ action: 'CREATE VIEW', target: 'primary',
    result: result.result || 'ERROR', latency_ms: result.latency_ms || 0 });
  showExplanation('views');
  highlightExpStep(1);
  showResult(
    result.error ? 'ERROR' : `VIEW CREATED (${result.rows} rows)`,
    result.latency_ms || 0, result,
    result.error ? 'rolled-back' : 'committed',
    result
  );
  await updateSidebar();
}

async function doViewsDrop() {
  const result = await apiPost('/api/views/drop', {});
  logEvent({ action: 'DROP VIEW', target: 'primary',
    result: result.result, latency_ms: result.latency_ms });
  await updateSidebar();
}

async function doViewsJoin() {
  if (animating) return;
  animating = true;
  setButtonsDisabled(true);
  clearAnimations();
  showExplanation('views');
  highlightExpStep(0);

  const result = await apiPost('/api/views/query-join', {});

  for (const step of result.steps) {
    logEvent(step);
    await animateArrow('arrow-app-primary', 'dot-app-primary',
      'latency-app-primary', step.latency_ms, 'arrow-op');
    await sleep(STEP_PAUSE_MS / 2);
  }

  showResult(
    `JOIN: ${result.row_count} rows`,
    result.total_ms, result.steps.map(s => ({
      action: s.action, result: s.result, ms: s.latency_ms,
    })), 'committed',
    result
  );

  animating = false;
  setButtonsDisabled(false);
}

async function doViewsView() {
  if (animating) return;
  animating = true;
  setButtonsDisabled(true);
  clearAnimations();
  showExplanation('views');
  highlightExpStep(1);

  const result = await apiPost('/api/views/query-view', {});

  if (result.error) {
    showResult('ERROR', 0, result, 'rolled-back');
    animating = false;
    setButtonsDisabled(false);
    return;
  }

  for (const step of result.steps) {
    logEvent(step);
    await animateArrow('arrow-app-primary', 'dot-app-primary',
      'latency-app-primary', step.latency_ms, 'arrow-success');
  }

  showResult(
    `VIEW: ${result.row_count} rows`,
    result.total_ms, result.steps.map(s => ({
      action: s.action, result: s.result, ms: s.latency_ms,
    })), 'committed',
    result
  );

  animating = false;
  setButtonsDisabled(false);
}

async function doViewsRefresh() {
  const result = await apiPost('/api/views/refresh', {});
  logEvent({ action: 'REFRESH VIEW', target: 'primary',
    result: result.result || 'ERROR', latency_ms: result.latency_ms || 0 });
  showExplanation('views');
  highlightExpStep(2);
  showResult(
    result.error ? 'ERROR' : `VIEW REFRESHED (${result.rows} rows)`,
    result.latency_ms || 0, result,
    result.error ? 'rolled-back' : 'committed',
    result
  );
}

// --- Vertical Scaling Actions ---

async function doVerticalSet() {
  const size = $('#vert-buffer').value;
  const label = $('#vert-buffer').options[$('#vert-buffer').selectedIndex].text;
  const result = await apiPost('/api/vertical/set-buffer', { size });
  logEvent({ action: `SET BUFFER ${label}`, target: 'primary',
    result: result.error ? 'ERROR' : 'OK', latency_ms: result.latency_ms || 0 });
  showExplanation('vertical');
  highlightExpStep(0);
  if (result.error) {
    showResult('ERROR', 0, result, 'rolled-back');
  } else {
    showResult(`Buffer pool set to ${label}`, result.latency_ms, result, 'committed', result);
  }
}

async function doVerticalBench() {
  if (animating) return;
  animating = true;
  setButtonsDisabled(true);
  clearAnimations();
  showExplanation('vertical');
  highlightExpStep(1);

  const result = await apiPost('/api/vertical/benchmark', { count: 200 });

  if (result.error) {
    showResult('ERROR', 0, result, 'rolled-back');
    animating = false;
    setButtonsDisabled(false);
    return;
  }

  // Animate a few representative arrows
  for (let i = 0; i < 3; i++) {
    await animateArrow('arrow-app-primary', 'dot-app-primary',
      'latency-app-primary', result.stats.avg_latency_ms, 'arrow-op');
    await sleep(100);
  }

  highlightExpStep(2);
  const s = result.stats;
  showResult(
    `${s.queries} queries | ${s.avg_latency_ms}ms avg | ${s.buffer_hit_ratio}% hit ratio`,
    result.total_ms,
    {
      buffer_pool_size: s.buffer_pool_size,
      avg_latency_ms: s.avg_latency_ms,
      p95_latency_ms: s.p95_latency_ms,
      queries_per_sec: s.queries_per_sec,
      buffer_hit_ratio: `${s.buffer_hit_ratio}%`,
      memory_reads: s.memory_reads,
      disk_reads: s.disk_reads,
    },
    s.buffer_hit_ratio > 90 ? 'committed' : 'rolled-back',
    result
  );

  await updateSidebar();
  animating = false;
  setButtonsDisabled(false);
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

  // Draggable resize handle for bottom bar
  const handle = $('#resize-handle');
  const bar = document.querySelector('.bottom-bar');
  if (handle && bar) {
    let dragging = false;
    let startY = 0;
    let startH = 0;

    handle.addEventListener('mousedown', (e) => {
      dragging = true;
      startY = e.clientY;
      startH = bar.offsetHeight;
      document.body.style.cursor = 'ns-resize';
      document.body.style.userSelect = 'none';
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!dragging) return;
      const diff = startY - e.clientY;
      const newH = Math.max(120, Math.min(startH + diff, window.innerHeight * 0.7));
      bar.style.height = newH + 'px';
    });

    document.addEventListener('mouseup', () => {
      if (dragging) {
        dragging = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    });
  }
}

function initButtons() {
  $('#repl-write').addEventListener('click', doReplication);
  $('#tx-transfer').addEventListener('click', doTransfer);
  $('#idx-explain').addEventListener('click', doExplain);
  $('#idx-add').addEventListener('click', doAddIndex);
  $('#idx-drop').addEventListener('click', doDropIndex);
  $('#cap-stop').addEventListener('click', doCapStop);
  $('#cap-start').addEventListener('click', doCapStart);
  $('#cap-test').addEventListener('click', doCapTest);
  $('#views-create').addEventListener('click', doViewsCreate);
  $('#views-drop').addEventListener('click', doViewsDrop);
  $('#views-join').addEventListener('click', doViewsJoin);
  $('#views-view').addEventListener('click', doViewsView);
  $('#views-refresh').addEventListener('click', doViewsRefresh);
  $('#vert-set').addEventListener('click', doVerticalSet);
  $('#vert-bench').addEventListener('click', doVerticalBench);
  $('#btn-reset-db').addEventListener('click', doReset);
}

function startPolling() {
  updateSidebar();
  pollTimer = setInterval(updateSidebar, POLL_INTERVAL_MS);
}

// --- Tooltips (JS-driven, fixed positioning) ---

function initTooltips() {
  const popup = $('#tooltip-popup');
  if (!popup) return;

  document.addEventListener('mouseover', (e) => {
    const el = e.target.closest('[data-tooltip]');
    if (!el) {
      popup.classList.remove('visible');
      return;
    }
    popup.textContent = el.dataset.tooltip;
    popup.classList.add('visible');

    // Position above the element
    const rect = el.getBoundingClientRect();
    const popupW = popup.offsetWidth;
    const popupH = popup.offsetHeight;
    let left = rect.left + rect.width / 2 - popupW / 2;
    let top = rect.top - popupH - 8;

    // Keep within viewport
    if (left < 8) left = 8;
    if (left + popupW > window.innerWidth - 8) {
      left = window.innerWidth - popupW - 8;
    }
    // If no room above, show below
    if (top < 8) {
      top = rect.bottom + 8;
    }

    popup.style.left = left + 'px';
    popup.style.top = top + 'px';
  });

  document.addEventListener('mouseout', (e) => {
    const el = e.target.closest('[data-tooltip]');
    if (!el) return;
    // Only hide if we're leaving the tooltip target
    const related = e.relatedTarget;
    if (related && el.contains(related)) return;
    popup.classList.remove('visible');
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initButtons();
  initConsole();
  initTooltips();
  startPolling();
  showExplanation('replication');
});
