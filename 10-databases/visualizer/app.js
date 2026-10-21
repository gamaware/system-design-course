'use strict';

const STEP_ARROW_MS = 300;
const STEP_PAUSE_MS = 500;
const POLL_INTERVAL_MS = 3000;
const MAX_LOG_ENTRIES = 100;

const PATTERN_DESCRIPTIONS = {
  replication: 'Write to primary, read from replica. Observe replication lag in real time.',
  consistency:
    'Transfer enrollment between courses inside an ACID transaction. Observe commit or rollback.',
  schema: 'Run EXPLAIN to see query plans. Add/drop indexes and compare rows scanned.',
  cap: 'Stop replication to simulate a network partition. Write data and observe divergence between primary and replica.',
  views:
    'Compare an expensive JOIN query with a pre-computed materialized view. The view reads fast but goes stale until you refresh it.',
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
        'We read the row from the replica every 5 ms (up to 1.5 s) and report how long after the commit it appeared.',
    },
    {
      title: '3. Check Replication Lag',
      detail:
        'SHOW REPLICA STATUS reveals Seconds_Behind_Source. ' +
        'It counts whole seconds, so sub-second lag shows as 0; under heavy load it grows.',
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
        'If the student is not enrolled, the DELETE affects 0 rows and the transaction rolls back.',
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
        'JOIN students + enrollments + courses and count the access_log rows of each student. ' +
        'The whole result is recomputed on every query, so it is always current but slow at scale.',
    },
    {
      title: '2. Materialized View (Pre-computed)',
      detail:
        'CREATE TABLE ... AS SELECT stores the result of that same query in a single flat table. ' +
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
        '200 random range queries read the 72 MB bench_data table. With a small buffer, many reads go to disk (slow). ' +
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

// --- Presentation helpers (theme, icons, status wording) ---

const THEME_KEY = 'lab10-visualizer-theme';

// Buttons whose label the empty result state points to, per tab. Defaults to the
// tab's primary button; CAP and Views start with a different step in the lab guide.
const FIRST_ACTION = { cap: '#cap-stop', views: '#views-join' };

const ICONS = {
  ok: '<path d="M20 6 9 17l-5-5" />',
  err: '<circle cx="12" cy="12" r="9" /><path d="M12 7.5v5.5M12 16.5h.01" />',
  info: '<circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 7.5h.01" />',
};

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const label = document.querySelector('#btn-theme-label');
  if (label) label.textContent = theme === 'dark' ? 'Light theme' : 'Dark theme';
}

try {
  if (localStorage.getItem(THEME_KEY) === 'dark') applyTheme('dark');
} catch {
  // storage unavailable (private mode): keep the default light theme
}

function iconSvg(name) {
  return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ICONS.info}</svg>`;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// Map a step result string to a visual tone: ok, warn or err.
const ERR_WORDS =
  /error|fail|violation|rolled|not found|not enrolled|not running|incomplete|denied|refused/;

function toneOf(text) {
  const t = String(text ?? '').toLowerCase();
  if (ERR_WORDS.test(t)) return 'err';
  if (/not yet|not in sync|stale|stopped|lag|diverged|partition/.test(t)) return 'warn';
  return 'ok';
}

function prefersReducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function currentTab() {
  return document.querySelector('.tab.active')?.dataset.tab || 'replication';
}

function $(sel) {
  return document.querySelector(sel);
}
function $$(sel) {
  return document.querySelectorAll(sel);
}
function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

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

  steps.forEach((step) => {
    if (!step.sql) return;
    const qDiv = document.createElement('div');
    qDiv.className = 'console-query';
    qDiv.textContent = `mysql(${step.target})> ${step.sql}`;
    output.appendChild(qDiv);

    const rDiv = document.createElement('div');
    rDiv.className = toneOf(step.result) === 'ok' ? 'console-meta' : 'console-error';
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
  $$('button').forEach((b) => {
    b.disabled = d;
  });
  document.body.classList.toggle('is-busy', d);
  $('#main-area')?.setAttribute('aria-busy', String(d));
  const panel = $('#result-panel');
  if (panel) {
    panel.classList.toggle('is-running', d);
    if (d) renderResultRunning();
  }
}

function clearAnimations() {
  $$('.arrow').forEach((a) => {
    a.classList.remove('arrow-active', 'arrow-success', 'arrow-op', 'arrow-error');
  });
  $$('.travel-dot').forEach((d) => d.setAttribute('opacity', '0'));
  $$('.latency-group').forEach((g) => {
    g.setAttribute('opacity', '0');
    const t = g.querySelector('.latency-label');
    if (t) t.textContent = '';
  });
  $$('.node-badge').forEach((b) => b.setAttribute('opacity', '0'));
}

// --- Arrow Animation ---

async function animateArrow(arrowId, dotId, latencyId, ms, cls) {
  const arrow = $(`#${arrowId}`);
  const dot = $(`#${dotId}`);
  const latGroup = $(`#${latencyId}`);

  if (arrow) {
    arrow.classList.remove('arrow-success', 'arrow-op', 'arrow-error');
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
  const tone = toneOf(step.result);
  const resultCls = tone === 'err' ? 'error' : tone;

  entry.append(
    el('span', 'log-time', time),
    el('span', 'log-action', step.action),
    el('span', `log-target ${targetCls}`, step.target),
    el('span', `log-result ${resultCls}`, step.result ?? 'ERROR'),
    el('span', 'log-latency', `${Number(step.latency_ms || 0).toFixed(1)}ms`),
  );

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

  container.replaceChildren(
    ...items.map((item, i) => {
      // Titles carry their own number ("1. INSERT on Primary"): show it as a badge.
      const match = /^(\d+)\.\s*(.*)$/.exec(item.title);
      const li = el('li', 'explanation-step');
      li.id = `exp-step-${i}`;
      const body = el('div');
      body.append(el('h3', '', match ? match[2] : item.title), el('p', '', item.detail));
      li.append(el('span', 'step-num', match ? match[1] : String(i + 1)), body);
      return li;
    }),
  );
  panel.classList.remove('hidden');
}

function highlightExpStep(index) {
  $$('.explanation-step').forEach((step, i) => {
    step.classList.toggle('active', i === index);
  });
}

// --- Result Panel ---

const COLUMN_LABELS = { action: 'Step', result: 'Result', ms: 'Time (ms)' };
const HIDDEN_RESULT_KEYS = new Set(['interpretation', 'steps']);
const CONNECTION_ERROR = /connect|connection|gone away|lost|refused|timed out|timeout/i;

function isNumeric(v) {
  return typeof v === 'number' || /^-?\d+(\.\d+)?$/.test(String(v));
}

function formatValue(v) {
  if (v === null || v === undefined) return 'NULL';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

function clearResultExtras(panel) {
  panel.querySelector('.result-interpretation')?.remove();
}

function renderResultEmpty(tab) {
  const panel = $('#result-panel');
  if (!panel) return;
  const btn = $(FIRST_ACTION[tab] || `#controls-${tab} .btn-primary`);
  const label = btn ? btn.textContent.trim() : 'a button above';

  panel.classList.remove('hidden');
  panel.dataset.state = 'empty';
  $('#result-status').className = 'result-status';
  $('#result-status').textContent = '';
  $('#result-latency').textContent = '';
  $('#result-data').textContent = '';
  clearResultExtras(panel);

  const empty = el('div', 'result-empty');
  const hint = el('p');
  hint.append('Press ', el('b', '', label), ' to run this experiment. ');
  hint.append('Each step lights up on the diagram and the outcome appears here.');
  empty.append(el('span', 'result-empty-title', 'No result yet'), hint);
  $('#result-body').replaceChildren(empty);
}

function renderResultRunning() {
  const panel = $('#result-panel');
  panel.dataset.state = 'neutral';
  $('#result-status').className = 'result-status';
  $('#result-status').textContent = 'Running…';
  $('#result-latency').textContent = '';
  $('#result-body').replaceChildren(
    el('p', 'result-hint', 'Watch the diagram and the steps below.'),
  );
  $('#result-data').textContent = '';
  clearResultExtras(panel);
}

function renderErrorBody(message) {
  const wrap = el('div');
  wrap.append(el('p', 'result-error-message', message));
  if (CONNECTION_ERROR.test(message)) {
    wrap.append(
      el(
        'p',
        'result-hint',
        'MySQL may still be starting: it takes about a minute after ./setup.sh. ' +
          'Wait, then try again. If it keeps failing, check the containers with docker ps.',
      ),
    );
  }
  return wrap;
}

// Render API data as a table (list of steps) or key/value list (plan, stats).
function renderResultData(data) {
  if (data && typeof data === 'object' && !Array.isArray(data) && data.error) {
    return renderErrorBody(String(data.error));
  }

  if (Array.isArray(data) && data.length && data.every((r) => r && typeof r === 'object')) {
    const cols = [...new Set(data.flatMap((r) => Object.keys(r)))];
    const table = el('table', 'result-table');
    const head = el('tr');
    cols.forEach((c) => {
      const th = el('th', isNumeric(data[0][c]) ? 'num' : '', COLUMN_LABELS[c] || c);
      th.scope = 'col';
      head.append(th);
    });
    const tbody = el('tbody');
    data.forEach((row) => {
      const tr = el('tr');
      cols.forEach((c) => {
        const v = row[c];
        let cls = isNumeric(v) ? 'num' : '';
        if (c === 'result') cls = `val-${toneOf(v)}`;
        tr.append(el('td', cls, formatValue(v)));
      });
      tbody.append(tr);
    });
    const thead = el('thead');
    thead.append(head);
    table.append(thead, tbody);
    return table;
  }

  if (data && typeof data === 'object' && !Array.isArray(data)) {
    const entries = Object.entries(data).filter(([k]) => !HIDDEN_RESULT_KEYS.has(k));
    if (entries.length === 0) return null;
    const dl = el('dl', 'kv-list');
    entries.forEach(([k, v]) => dl.append(el('dt', '', k), el('dd', '', formatValue(v))));
    return dl;
  }

  return null;
}

function showResult(status, latency, data, cls, apiResult, latencyLabel = 'total') {
  const panel = $('#result-panel');
  const statusEl = $('#result-status');
  const latencyEl = $('#result-latency');
  const dataEl = $('#result-data');

  const tone = cls === 'committed' ? 'ok' : cls === 'rolled-back' ? 'err' : 'neutral';
  panel.dataset.state = tone;
  statusEl.className = `result-status ${cls || ''}`;
  statusEl.innerHTML = iconSvg(tone === 'neutral' ? 'info' : tone);
  statusEl.append(el('span', '', status));
  latencyEl.textContent = `${Number(latency || 0).toFixed(1)}ms ${latencyLabel}`;
  dataEl.textContent = JSON.stringify(data, null, 2);
  panel.classList.remove('hidden');

  const rendered = renderResultData(data);
  $('#result-body').replaceChildren(...(rendered ? [rendered] : []));

  // Interpretation: what the result means, in plain language
  clearResultExtras(panel);
  if (apiResult?.interpretation) {
    const iDiv = el('div', 'result-interpretation');
    iDiv.append(el('strong', '', 'What this means'), apiResult.interpretation);
    panel.insertBefore(iDiv, panel.querySelector('.result-raw'));
  }

  panel.scrollIntoView({ block: 'nearest', behavior: prefersReducedMotion() ? 'auto' : 'smooth' });

  // Log SQL queries to the console (without interpretation)
  if (apiResult) {
    logSqlToConsole(apiResult);
  }
}

// A request that never got an answer (server down, network error).
function showUnreachable() {
  const panel = $('#result-panel');
  if (!panel) return;
  panel.classList.remove('is-running');
  panel.dataset.state = 'err';
  $('#result-status').className = 'result-status rolled-back';
  $('#result-status').innerHTML = iconSvg('err');
  $('#result-status').append(el('span', '', 'No response from the visualizer'));
  $('#result-latency').textContent = '';
  clearResultExtras(panel);
  $('#result-body').replaceChildren(
    el(
      'p',
      'result-hint',
      'The request did not reach the server. Check that the lab containers are running ' +
        '(docker ps), then reload this page.',
    ),
  );
}

// --- Sidebar Update ---

function threadTone(value) {
  if (value === 'Yes') return 'ok';
  if (value === 'No') return 'err';
  return value ? 'warn' : '';
}

function setHealth(tone, title, detail) {
  const box = $('#repl-health');
  if (!box) return;
  box.dataset.state = tone;
  $('#repl-health-title').textContent = title;
  $('#repl-health-detail').textContent = detail;
}

// Turn the raw replica status into one sentence a class can read from the back row.
function renderReplicationHealth(state) {
  const r = state.replica || {};
  const io = r.io_running;
  const sql = r.sql_running;
  const lag = r.lag;
  const diagram = $('#diagram');
  let partitioned = false;
  let lagging = false;

  if (!io && !sql) {
    setHealth(
      'warn',
      'Replication not configured',
      'The replica reports no replication status. Run ./setup.sh again to configure it.',
    );
  } else if (io === 'Connecting') {
    lagging = true;
    setHealth(
      'warn',
      'Replica connecting…',
      'The replica is reconnecting to the primary. Wait a few seconds.',
    );
  } else if (io !== 'Yes' || sql !== 'Yes') {
    partitioned = true;
    setHealth(
      'err',
      'Replication stopped',
      `IO thread: ${io || '--'}, SQL thread: ${sql || '--'}. New writes stay on the primary ` +
        'until you click Start Replication (CAP Theorem tab).',
    );
  } else if (typeof lag === 'number' && lag > 0) {
    lagging = true;
    setHealth(
      'warn',
      `Replica ${lag} s behind`,
      'Reads from the replica can return stale data until it catches up.',
    );
  } else {
    setHealth('ok', 'In sync', 'The replica has applied every change from the primary.');
  }

  if (diagram) {
    diagram.classList.toggle('is-partitioned', partitioned);
    diagram.classList.toggle('is-lagging', lagging);
  }
}

function renderRowDiff(state) {
  const p = state.primary?.students;
  const r = state.replica?.students;
  const note = $('#row-diff');
  const replicaRows = $('#stat-replica-rows');
  const differs = typeof p === 'number' && typeof r === 'number' && p !== r;
  replicaRows.classList.toggle('warn', differs);
  if (!note) return;
  note.hidden = !differs;
  if (differs) {
    const n = Math.abs(p - r);
    note.textContent = `Replica has ${n} ${n === 1 ? 'row' : 'rows'} ${
      p > r ? 'fewer' : 'more'
    } than the primary.`;
  }
}

function setFreshness(live) {
  const f = $('#state-freshness');
  if (!f) return;
  f.dataset.state = live ? 'live' : 'offline';
  // While offline the numbers below are the last known values: show them as stale.
  document.querySelector('.sidebar')?.classList.toggle('is-stale', !live);
  f.textContent = live ? `Live · every ${POLL_INTERVAL_MS / 1000} s` : 'Offline';
}

async function updateSidebar() {
  try {
    const state = await apiGet('/api/db/state');

    $('#stat-io').textContent = state.replica?.io_running || '--';
    $('#stat-io').className = `stat-value ${threadTone(state.replica?.io_running)}`;

    $('#stat-sql').textContent = state.replica?.sql_running || '--';
    $('#stat-sql').className = `stat-value ${threadTone(state.replica?.sql_running)}`;

    const lag = state.replica?.lag;
    $('#stat-lag').textContent = lag !== null && lag !== undefined ? lag : '--';
    $('#stat-lag').className = 'stat-value stat-big ' + (lag === 0 ? 'ok' : 'warn');

    $('#stat-primary-rows').textContent = state.primary?.students || '--';
    $('#stat-replica-rows').textContent = state.replica?.students || '--';
    const logRows = state.primary?.access_log_rows;
    $('#stat-log-rows').textContent =
      typeof logRows === 'number' && logRows ? logRows.toLocaleString('en-US') : logRows || '--';

    // Courses
    $('#course-list').replaceChildren(
      ...(state.primary?.courses || []).map((c) => {
        const li = el('li', 'course-item');
        const count = el('span', 'course-enrolled');
        count.append(el('b', '', String(c.enrolled)), ' enrolled');
        li.append(el('span', 'course-code', c.code), count);
        return li;
      }),
    );

    // Indexes
    const indexes = state.primary?.indexes || [];
    const unique = [...new Set(indexes)];
    $('#index-list').replaceChildren(
      ...(unique.length > 0 ? unique.map((name) => el('span', 'index-chip', name)) : ['None']),
    );

    renderReplicationHealth(state);
    renderRowDiff(state);
    setFreshness(true);
  } catch {
    // Keep polling; tell the class what is going on in the meantime.
    setFreshness(false);
    setHealth(
      'err',
      'Database unreachable',
      'The visualizer cannot read MySQL. Right after ./setup.sh this is normal for about a ' +
        'minute; otherwise check the containers with docker ps. Retrying every 3 seconds.',
    );
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
  const email =
    name.toLowerCase().replace(/\s+/g, '.') + Math.floor(Math.random() * 9999) + '@university.edu';

  const result = await apiPost('/api/replication/write', { name, email, major });

  if (result.error) {
    showResult('ERROR', 0, result, 'rolled-back');
    animating = false;
    setButtonsDisabled(false);
    return;
  }

  for (const step of result.steps) {
    if (step.action === 'INSERT') highlightExpStep(0);
    else if (step.action.startsWith('SELECT')) highlightExpStep(1);
    else highlightExpStep(2);
    logEvent(step);

    if (step.action === 'INSERT') {
      await animateArrow(
        'arrow-app-primary',
        'dot-app-primary',
        'latency-app-primary',
        step.latency_ms,
        'arrow-op',
      );
    } else if (step.action.startsWith('SELECT')) {
      const cls = step.result === 'FOUND' ? 'arrow-success' : 'arrow-error';
      await animateArrow(
        'arrow-app-replica',
        'dot-app-replica',
        'latency-app-replica',
        step.latency_ms,
        cls,
      );
    }
    await sleep(STEP_PAUSE_MS);
  }

  showResult(
    result.replicated ? 'REPLICATED' : 'NOT YET REPLICATED',
    result.total_ms,
    result.steps.map((s) => ({ action: s.action, result: s.result, ms: s.latency_ms })),
    result.replicated ? 'committed' : 'rolled-back',
    result,
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
    student_id: studentId,
    from_course: fromCourse,
    to_course: toCourse,
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
      await animateArrow(
        'arrow-app-primary',
        'dot-app-primary',
        'latency-app-primary',
        step.latency_ms,
        'arrow-op',
      );
    } else if (step.action.startsWith('DELETE') || step.action.startsWith('UPDATE')) {
      if (expIdx < 1) expIdx = 1;
      highlightExpStep(expIdx);
      await animateArrow(
        'arrow-app-primary',
        'dot-app-primary',
        'latency-app-primary',
        step.latency_ms,
        step.result === 'OK' ? 'arrow-op' : 'arrow-error',
      );
    } else if (step.action.startsWith('INSERT')) {
      expIdx = 2;
      highlightExpStep(2);
      const cls = step.result === 'OK' ? 'arrow-success' : 'arrow-error';
      await animateArrow(
        'arrow-app-primary',
        'dot-app-primary',
        'latency-app-primary',
        step.latency_ms,
        cls,
      );
    } else if (step.action === 'COMMIT' || step.action === 'ROLLBACK') {
      highlightExpStep(3);
      const cls = step.action === 'COMMIT' ? 'arrow-success' : 'arrow-error';
      await animateArrow(
        'arrow-app-primary',
        'dot-app-primary',
        'latency-app-primary',
        step.latency_ms,
        cls,
      );
    }
    await sleep(STEP_PAUSE_MS / 2);
  }

  const committed = result.outcome === 'COMMITTED';
  showResult(
    result.outcome,
    result.total_ms,
    result.steps.map((s) => ({ action: s.action, result: s.result, ms: s.latency_ms })),
    committed ? 'committed' : 'rolled-back',
    result,
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
    student_id: studentId,
    resource,
  });

  if (result.error) {
    showResult('ERROR', 0, result, 'rolled-back');
    animating = false;
    setButtonsDisabled(false);
    return;
  }

  highlightExpStep(0);
  for (const step of result.steps) {
    logEvent(step);
    await animateArrow(
      'arrow-app-primary',
      'dot-app-primary',
      'latency-app-primary',
      step.latency_ms,
      'arrow-op',
    );
    await sleep(STEP_PAUSE_MS);
  }

  const plan = result.steps[0]?.data || {};
  const rows = plan.rows || plan.row || '?';
  const keyUsed = plan.key || 'NONE (full scan)';
  const fullScan = !plan.key || plan.type === 'ALL';

  showResult(
    `Rows scanned: ${rows} | Key: ${keyUsed}`,
    result.total_ms,
    plan,
    fullScan ? 'rolled-back' : 'committed',
    result,
  );

  await updateSidebar();
  animating = false;
  setButtonsDisabled(false);
}

// Add Index / Drop Index replace the result panel with their own outcome.
async function doIndexChange(url, verb) {
  if (animating) return;
  animating = true;
  setButtonsDisabled(true);
  clearAnimations();
  showExplanation('schema');
  highlightExpStep(1);

  const result = await apiPost(url, {});
  if (result.error) {
    showResult('ERROR', 0, result, 'rolled-back');
  } else {
    result.steps.forEach(logEvent);
    await animateArrow(
      'arrow-app-primary',
      'dot-app-primary',
      'latency-app-primary',
      result.latency_ms,
      'arrow-op',
    );
    const changed = result.result === 'CREATED' || result.result === 'DROPPED';
    showResult(
      changed ? `INDEX ${verb} ${result.index}` : `INDEX ${result.result} ${result.index}`,
      result.latency_ms,
      result.steps.map((s) => ({ action: s.action, result: s.result, ms: s.latency_ms })),
      changed ? 'committed' : '',
      result,
    );
  }

  await updateSidebar();
  animating = false;
  setButtonsDisabled(false);
}

function doAddIndex() {
  return doIndexChange('/api/schema/add-index', 'CREATED');
}

function doDropIndex() {
  return doIndexChange('/api/schema/drop-index', 'DROPPED');
}

// --- CAP Theorem Actions ---

async function doCapStop() {
  const result = await apiPost('/api/cap/stop-replication', {});
  logEvent({
    action: 'STOP REPLICA',
    target: 'replica',
    result: result.result,
    latency_ms: result.latency_ms,
  });
  showExplanation('cap');
  highlightExpStep(0);
  // Visual: grey out replica node
  const replicaRect = document.querySelector('#node-replica rect');
  if (replicaRect) replicaRect.style.opacity = '0.4';
  showResult(
    'PARTITION ACTIVE',
    result.latency_ms,
    { message: 'Replication stopped. Replica will not receive new writes.' },
    'rolled-back',
    result,
  );
  await updateSidebar();
}

async function doCapStart() {
  const result = await apiPost('/api/cap/start-replication', {});
  logEvent({
    action: 'START REPLICA',
    target: 'replica',
    result: result.result,
    latency_ms: result.latency_ms,
  });
  showExplanation('cap');
  highlightExpStep(2);
  // Visual: restore replica node
  const replicaRect = document.querySelector('#node-replica rect');
  if (replicaRect) replicaRect.style.opacity = '1';
  showResult(
    'PARTITION RECOVERED',
    result.latency_ms,
    { message: 'Replication resumed. Replica is catching up.' },
    'committed',
    result,
  );
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
      await animateArrow(
        'arrow-app-primary',
        'dot-app-primary',
        'latency-app-primary',
        step.latency_ms,
        'arrow-op',
      );
    } else if (step.action === 'SELECT (primary)') {
      highlightExpStep(1);
      await animateArrow(
        'arrow-app-primary',
        'dot-app-primary',
        'latency-app-primary',
        step.latency_ms,
        'arrow-success',
      );
    } else if (step.action === 'SHOW REPLICA STATUS') {
      highlightExpStep(step.result.includes('STOPPED') ? 0 : 2);
    } else if (step.action === 'SELECT (replica)') {
      highlightExpStep(1);
      const cls = step.result.includes('stale') ? 'arrow-error' : 'arrow-success';
      await animateArrow(
        'arrow-app-replica',
        'dot-app-replica',
        'latency-app-replica',
        step.latency_ms,
        cls,
      );
    }
    await sleep(STEP_PAUSE_MS);
  }

  const diverged = result.outcome.includes('DIVERGED');
  showResult(
    result.outcome,
    result.total_ms,
    result.steps.map((s) => ({ action: s.action, result: s.result, ms: s.latency_ms })),
    diverged ? 'rolled-back' : 'committed',
    result,
  );

  await updateSidebar();
  animating = false;
  setButtonsDisabled(false);
}

// --- Materialized Views Actions ---

async function doViewsCreate() {
  const result = await apiPost('/api/views/create', {});
  logEvent({
    action: 'CREATE VIEW',
    target: 'primary',
    result: result.result || 'ERROR',
    latency_ms: result.latency_ms || 0,
  });
  showExplanation('views');
  highlightExpStep(1);
  showResult(
    result.error ? 'ERROR' : `VIEW CREATED (${result.rows} rows)`,
    result.latency_ms || 0,
    result,
    result.error ? 'rolled-back' : 'committed',
    result,
  );
  await updateSidebar();
}

async function doViewsDrop() {
  const result = await apiPost('/api/views/drop', {});
  logEvent({
    action: 'DROP VIEW',
    target: 'primary',
    result: result.result,
    latency_ms: result.latency_ms,
  });
  await updateSidebar();
}

// The result panel is narrow: show the columns that tell rows apart.
function viewRows(rows) {
  return rows.map((r) => ({ name: r.name, code: r.code, title: r.title, accesses: r.accesses }));
}

async function doViewsJoin() {
  if (animating) return;
  animating = true;
  setButtonsDisabled(true);
  clearAnimations();
  showExplanation('views');
  highlightExpStep(0);

  const result = await apiPost('/api/views/query-join', {});

  if (result.error) {
    showResult('ERROR', 0, result, 'rolled-back');
    animating = false;
    setButtonsDisabled(false);
    return;
  }

  for (const step of result.steps) {
    logEvent(step);
    await animateArrow(
      'arrow-app-primary',
      'dot-app-primary',
      'latency-app-primary',
      step.latency_ms,
      'arrow-op',
    );
    await sleep(STEP_PAUSE_MS / 2);
  }

  showResult(
    `JOIN: ${result.row_count} rows`,
    result.query_ms,
    viewRows(result.rows),
    'committed',
    result,
    'query',
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
    await animateArrow(
      'arrow-app-primary',
      'dot-app-primary',
      'latency-app-primary',
      step.latency_ms,
      'arrow-success',
    );
  }

  showResult(
    `VIEW: ${result.row_count} rows`,
    result.query_ms,
    viewRows(result.rows),
    'committed',
    result,
    'query',
  );

  animating = false;
  setButtonsDisabled(false);
}

async function doViewsRefresh() {
  const result = await apiPost('/api/views/refresh', {});
  logEvent({
    action: 'REFRESH VIEW',
    target: 'primary',
    result: result.result || 'ERROR',
    latency_ms: result.latency_ms || 0,
  });
  showExplanation('views');
  highlightExpStep(2);
  showResult(
    result.error ? 'ERROR' : `VIEW REFRESHED (${result.rows} rows)`,
    result.latency_ms || 0,
    result,
    result.error ? 'rolled-back' : 'committed',
    result,
  );
}

// --- Vertical Scaling Actions ---

function formatMb(bytes) {
  return `${Math.round(Number(bytes) / (1024 * 1024))} MB`;
}

async function doVerticalSet() {
  const size = $('#vert-buffer').value;
  const label = $('#vert-buffer').options[$('#vert-buffer').selectedIndex].text;
  if (animating) return;
  animating = true;
  setButtonsDisabled(true);
  showExplanation('vertical');
  highlightExpStep(0);
  const result = await apiPost('/api/vertical/set-buffer', { size });
  logEvent({
    action: `SET BUFFER ${label}`,
    target: 'primary',
    result: result.error ? 'ERROR' : 'OK',
    latency_ms: result.latency_ms || 0,
  });
  if (result.error) {
    showResult('ERROR', result.latency_ms || 0, result, 'rolled-back', result);
  } else {
    showResult(
      `Buffer pool is now ${formatMb(result.actual_size)}`,
      result.latency_ms,
      {
        previous_size: formatMb(result.previous_size),
        requested_size: formatMb(result.size),
        actual_size: formatMb(result.actual_size),
      },
      'committed',
      result,
    );
  }
  animating = false;
  setButtonsDisabled(false);
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
    await animateArrow(
      'arrow-app-primary',
      'dot-app-primary',
      'latency-app-primary',
      result.stats.avg_latency_ms,
      'arrow-op',
    );
    await sleep(100);
  }

  highlightExpStep(2);
  const s = result.stats;
  showResult(
    `${s.queries} queries | ${s.avg_latency_ms}ms avg | ${s.buffer_hit_ratio}% hit ratio`,
    result.total_ms,
    {
      buffer_pool_size: formatMb(s.buffer_pool_size),
      avg_latency_ms: s.avg_latency_ms,
      p95_latency_ms: s.p95_latency_ms,
      queries_per_sec: s.queries_per_sec,
      buffer_hit_ratio: `${s.buffer_hit_ratio}%`,
      memory_reads: s.memory_reads,
      disk_reads: s.disk_reads,
    },
    s.buffer_hit_ratio > 90 ? 'committed' : 'rolled-back',
    result,
  );

  await updateSidebar();
  animating = false;
  setButtonsDisabled(false);
}

// --- Reset ---

async function doReset() {
  if (animating) return;
  const ok = window.confirm(
    'Reset the database to its initial state?\n\n' +
      'This deletes added students, enrollments and access_log rows, drops the index and ' +
      'the materialized view, restarts replication and sets the buffer pool back to 128 MB.',
  );
  if (!ok) return;
  animating = true;
  setButtonsDisabled(true);
  const result = await apiPost('/api/db/reset', {});
  logSqlToConsole(result);
  logEvent({
    action: 'RESET DB',
    target: 'primary',
    result: result.error ? 'ERROR' : result.result || 'OK',
    latency_ms: (result.steps || []).reduce((sum, s) => sum + s.latency_ms, 0),
  });
  await updateSidebar();
  $('#vert-buffer').value = '134217728';
  const replicaRect = document.querySelector('#node-replica rect');
  if (replicaRect) replicaRect.style.opacity = '1';
  $('#explanation-panel').classList.add('hidden');
  clearAnimations();
  animating = false;
  setButtonsDisabled(false);
  if (result.error || result.result !== 'OK') {
    showResult('RESET INCOMPLETE', 0, { message: result.error || result.message }, 'rolled-back');
  } else {
    renderResultEmpty(currentTab());
  }
}

// --- Init ---

function initTabs() {
  $$('.tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      $$('.tab').forEach((t) => {
        t.classList.remove('active');
        t.removeAttribute('aria-current');
      });
      tab.classList.add('active');
      tab.setAttribute('aria-current', 'true');
      const target = tab.dataset.tab;
      const title = $('#experiment-title');
      if (title) title.textContent = tab.textContent.trim();
      $$('.controls').forEach((p) => {
        p.classList.toggle('active', p.id === `controls-${target}`);
      });
      const desc = $('#pattern-description');
      if (desc && PATTERN_DESCRIPTIONS[target]) {
        desc.textContent = PATTERN_DESCRIPTIONS[target];
      }
      showExplanation(target);
      clearAnimations();
      renderResultEmpty(target);
    });
  });
}

// --- SQL Console ---

const consoleHistory = [];
let consoleHistoryIndex = -1;

// Like the mysql client's \G: one "column: value" line per column, per row.
function renderVerticalRows(result) {
  const width = Math.max(...result.columns.map((c) => c.length));
  const stars = '*'.repeat(27);
  const lines = [];
  result.rows.slice(0, 20).forEach((row, i) => {
    lines.push(`${stars} ${i + 1}. row ${stars}`);
    result.columns.forEach((c) => lines.push(`${c.padStart(width)}: ${formatValue(row[c])}`));
  });
  if (result.rows.length > 20) lines.push(`(showing 20 of ${result.rows.length} rows)`);
  return el('div', 'console-vertical', lines.join('\n'));
}

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
  } else if (result.columns && result.vertical) {
    output.appendChild(renderVerticalRows(result));
    const meta = document.createElement('div');
    meta.className = 'console-meta';
    meta.textContent = `${result.row_count} row(s) in ${result.latency_ms}ms`;
    output.appendChild(meta);
  } else if (result.columns) {
    // Build HTML table
    const table = document.createElement('table');
    table.className = 'console-result-table';
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    result.columns.forEach((col) => {
      const th = document.createElement('th');
      th.scope = 'col';
      th.textContent = col;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    const maxRows = Math.min(result.rows.length, 20);
    for (let i = 0; i < maxRows; i++) {
      const tr = document.createElement('tr');
      result.columns.forEach((col) => {
        const td = document.createElement('td');
        const value = result.rows[i][col];
        td.textContent = value ?? 'NULL';
        if (value === null || value === undefined) td.className = 'null';
        else if (isNumeric(value)) td.className = 'num';
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    output.appendChild(table);

    const meta = document.createElement('div');
    meta.className = 'console-meta';
    const truncated = result.rows.length > 20 ? ` (showing 20 of ${result.rows.length})` : '';
    meta.textContent = `${result.row_count} row(s)${truncated} in ${result.latency_ms}ms`;
    output.appendChild(meta);
  } else {
    const metaDiv = document.createElement('div');
    metaDiv.className = 'console-meta';
    metaDiv.textContent = `${result.affected_rows} row(s) affected in ${result.latency_ms}ms`;
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
      consoleHistoryIndex = Math.min(consoleHistoryIndex + 1, consoleHistory.length - 1);
      $('#console-input').value = consoleHistory[consoleHistoryIndex];
    } else if (e.key === 'ArrowDown') {
      consoleHistoryIndex = Math.max(consoleHistoryIndex - 1, -1);
      $('#console-input').value =
        consoleHistoryIndex >= 0 ? consoleHistory[consoleHistoryIndex] : '';
    }
  });

  // Target toggle buttons
  $$('.target-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      $$('.target-btn').forEach((b) => b.classList.remove('active'));
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
  setInterval(updateSidebar, POLL_INTERVAL_MS);
}

// --- Tooltips (JS-driven, fixed positioning) ---

function initTooltips() {
  const popup = $('#tooltip-popup');
  if (!popup) return;

  function show(target) {
    popup.textContent = target.dataset.tooltip;
    popup.classList.add('visible');

    // Position above the element
    const rect = target.getBoundingClientRect();
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
  }

  document.addEventListener('mouseover', (e) => {
    const target = e.target.closest('[data-tooltip]');
    if (!target) {
      popup.classList.remove('visible');
      return;
    }
    show(target);
  });

  document.addEventListener('mouseout', (e) => {
    const target = e.target.closest('[data-tooltip]');
    if (!target) return;
    // Only hide if we're leaving the tooltip target
    const related = e.relatedTarget;
    if (related && target.contains(related)) return;
    popup.classList.remove('visible');
  });

  // Keyboard users get the same hint when a control receives focus.
  document.addEventListener('focusin', (e) => {
    const target = e.target.closest?.('[data-tooltip]');
    if (target && target.matches(':focus-visible')) show(target);
    else popup.classList.remove('visible');
  });
  document.addEventListener('focusout', () => popup.classList.remove('visible'));
}

function initTheme() {
  const btn = $('#btn-theme');
  if (!btn) return;
  applyTheme(document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');
  btn.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // storage unavailable: the choice lasts until reload
    }
  });
}

// Requests that fail before the server answers (container stopped, network error).
window.addEventListener('unhandledrejection', (e) => {
  console.error(e.reason);
  showUnreachable();
});

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initButtons();
  initConsole();
  initTooltips();
  initTheme();
  startPolling();
  showExplanation('replication');
  renderResultEmpty('replication');
});
