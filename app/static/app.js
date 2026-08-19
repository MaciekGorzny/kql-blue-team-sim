"use strict";

/* Lightweight KQL syntax highlighter for the query editor.
 *
 * Keyword matching is case-SENSITIVE on purpose: the engine's parser only
 * recognizes lowercase keywords (`where`, not `Where`), so highlighting
 * case-insensitively would show a query as "looks right" when the engine
 * would actually reject it.
 */
const KQL_KEYWORDS = new Set([
  "let", "where", "project", "extend", "summarize", "join", "sort", "order", "by",
  "take", "limit", "distinct", "count", "and", "or", "not", "in", "contains",
  "startswith", "endswith", "has", "matches", "regex", "asc", "desc",
  "kind", "on", "sum", "avg", "dcount", "min", "max", "tolower", "toupper",
  "strcat", "split", "ago", "now", "bin", "dynamic", "true", "false", "$left", "$right",
]);

const KQL_TOKEN_RE =
  /(\/\/[^\n]*)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(\d+(?:\.\d+)?(?:ms|d|h|m|s)?)|([A-Za-z_$][A-Za-z0-9_]*)|(==|!=|<=|>=|[|(),.;=<>+\-*/%[\]])/g;

function escapeHtml(text) {
  return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function highlightKql(code) {
  let out = "";
  let lastIndex = 0;
  KQL_TOKEN_RE.lastIndex = 0;
  let match;
  while ((match = KQL_TOKEN_RE.exec(code)) !== null) {
    out += escapeHtml(code.slice(lastIndex, match.index));
    const [, comment, string, number, ident, punct] = match;
    if (comment) {
      out += `<span class="tok-comment">${escapeHtml(comment)}</span>`;
    } else if (string) {
      out += `<span class="tok-string">${escapeHtml(string)}</span>`;
    } else if (number) {
      out += `<span class="tok-number">${escapeHtml(number)}</span>`;
    } else if (ident) {
      const cls = KQL_KEYWORDS.has(ident) ? "tok-keyword" : "tok-column";
      out += `<span class="${cls}">${escapeHtml(ident)}</span>`;
    } else if (punct) {
      out += `<span class="tok-punct">${escapeHtml(punct)}</span>`;
    }
    lastIndex = KQL_TOKEN_RE.lastIndex;
  }
  out += escapeHtml(code.slice(lastIndex));
  return out;
}

/* --- single-window shell: persistent sidebar + main panel ---
 *
 * The initial scenario list + the initially-selected scenario's detail are
 * embedded in the page (see scenario_shell.html) so first paint needs zero
 * fetches. Every later selection (sidebar click, prev/next, an import) goes
 * through the same renderSidebar()/renderScenarioInfo() functions, just fed
 * by a fetch() to the JSON API instead - one rendering implementation,
 * multiple data sources.
 *
 * The editor + result table are queried against ONE shared, ever-growing log
 * pool (every built-in table plus every imported scenario's own log rows -
 * see core/scenarios/log_store.py), not scoped to whichever scenario is
 * selected. So switching scenarios never touches the query text or result
 * table - buildMainPanelShell() builds the editor once, and renderScenarioInfo()
 * only ever replaces the task-info strip above it (title/prompt/hint/MITRE)
 * plus which scenario id "Uruchom" currently grades against.
 */

let currentScenarioId = null;
let currentScenarioTitle = "";
let currentScenarioSourceUrl = null;

// Set by renderScenarioInfo() whenever the scenario it's rendering is being
// viewed as a step of an incident (data.incident present); cleared for a
// plain scenario view. Only renderScenarioInfo itself and the incident-step
// nav handlers it wires up read this.
let currentIncidentContext = null;

// Must match SANDBOX_ID in app/routers/pages.py - the pseudo id that marks
// "free-query sandbox" mode instead of a real scenario id.
const SANDBOX_ID = "__sandbox__";

// Must match LESSON_ID_PREFIX in app/routers/pages.py - prefixing a lesson's
// own id lets currentScenarioId/routing tell "which lesson" apart from a
// scenario id or the sandbox id purely from the id string's shape.
const LESSON_ID_PREFIX = "lesson:";

// Must match INCIDENT_ID_PREFIX in app/routers/pages.py - used only for an
// incident *overview* page's pseudo id. A step page's currentScenarioId is
// the real scenario id it grades against (see renderScenarioInfo below).
const INCIDENT_ID_PREFIX = "incident:";

// "Solved" is purely a client-side convenience (which scenarios you've
// personally gotten a correct answer for at least once) - no server state,
// just a browser-local checklist that survives reloads.
const SOLVED_STORAGE_KEY = "btsim_solved_scenarios";

function getSolvedIds() {
  try {
    return new Set(JSON.parse(localStorage.getItem(SOLVED_STORAGE_KEY) || "[]"));
  } catch (err) {
    return new Set();
  }
}

function markSolved(scenarioId) {
  const solved = getSolvedIds();
  if (solved.has(scenarioId)) return;
  solved.add(scenarioId);
  try {
    localStorage.setItem(SOLVED_STORAGE_KEY, JSON.stringify([...solved]));
  } catch (err) {
    return; // localStorage unavailable (e.g. private mode) - fail silently
  }

  const item = document.querySelector(`.sidebar-item[data-scenario-id="${scenarioId}"]`);
  if (!item || item.classList.contains("solved")) return;
  item.classList.add("solved");
  const top = item.querySelector(".sidebar-item-top");
  if (top && !top.querySelector(".sidebar-item-solved")) {
    const badge = document.createElement("span");
    badge.className = "sidebar-item-solved";
    badge.title = "Rozwiązano";
    badge.textContent = "✓";
    top.appendChild(badge);
  }
}

// Progress on an incident's "action" (non-KQL) steps is likewise purely a
// client-side checklist - no scenario/grading involved at all, just which
// action-item checkboxes the trainee has ticked, keyed by "incidentId:step".
const ACTION_PROGRESS_KEY = "btsim_incident_action_progress";

function getActionProgress() {
  try {
    return JSON.parse(localStorage.getItem(ACTION_PROGRESS_KEY) || "{}");
  } catch (err) {
    return {};
  }
}

function isActionChecked(incidentId, stepNumber, actionIndex) {
  const progress = getActionProgress();
  const checked = progress[`${incidentId}:${stepNumber}`] || [];
  return checked.includes(actionIndex);
}

function toggleActionChecked(incidentId, stepNumber, actionIndex) {
  const progress = getActionProgress();
  const key = `${incidentId}:${stepNumber}`;
  const checked = new Set(progress[key] || []);
  if (checked.has(actionIndex)) {
    checked.delete(actionIndex);
  } else {
    checked.add(actionIndex);
  }
  progress[key] = [...checked];
  try {
    localStorage.setItem(ACTION_PROGRESS_KEY, JSON.stringify(progress));
  } catch (err) {
    // localStorage unavailable (e.g. private mode) - fail silently
  }
}

function isActionStepDone(incidentId, stepNumber, totalActions) {
  const progress = getActionProgress();
  const checked = progress[`${incidentId}:${stepNumber}`] || [];
  return totalActions > 0 && checked.length >= totalActions;
}

function difficultyBadge(scenario) {
  return `<span class="badge badge-${escapeHtml(scenario.difficulty)}">${escapeHtml(scenario.difficulty)}</span>`;
}

function mitreTagsHtml(techniques) {
  return techniques.map((t) => `<span class="mitre-tag">${escapeHtml(t)}</span>`).join("");
}

function renderDataTable(table, columns, rows) {
  table.innerHTML = "";
  if (!columns.length) return;

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const col of columns) {
    const th = document.createElement("th");
    th.textContent = col;
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    for (const col of columns) {
      const td = document.createElement("td");
      const value = row[col];
      td.textContent = value === null || value === undefined ? "null" : String(value);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
}

function renderSidebar(scenarios, activeId) {
  const list = document.getElementById("sidebar-list");
  list.innerHTML = "";
  const solvedIds = getSolvedIds();
  for (const s of scenarios) {
    const solved = solvedIds.has(s.id);
    const a = document.createElement("a");
    a.href = `/scenarios/${s.id}`;
    a.className = "sidebar-item" + (s.id === activeId ? " active" : "") + (solved ? " solved" : "");
    a.dataset.scenarioId = s.id;
    const solvedBadgeHtml = solved ? `<span class="sidebar-item-solved" title="Rozwiązano">✓</span>` : "";
    const deleteBtnHtml = s.is_imported
      ? `<button type="button" class="sidebar-item-delete" title="Usuń zaimportowane ćwiczenie" aria-label="Usuń zaimportowane ćwiczenie">✕</button>`
      : "";
    a.innerHTML = `
      <div class="sidebar-item-row">
        <span class="sidebar-item-title">${escapeHtml(s.title)}</span>
        ${deleteBtnHtml}
        ${solvedBadgeHtml}
        ${difficultyBadge(s)}
      </div>
    `;
    a.addEventListener("click", (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      selectScenario(s.id);
    });
    const deleteBtn = a.querySelector(".sidebar-item-delete");
    if (deleteBtn) {
      deleteBtn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        handleDeleteScenario(s.id, s.title);
      });
    }
    list.appendChild(a);
  }
}

async function handleDeleteScenario(id, title) {
  if (!confirm(`Usunąć zaimportowane ćwiczenie "${title}"? Tej operacji nie można cofnąć.`)) return;

  try {
    const response = await fetch(`/api/scenarios/${id}`, { method: "DELETE" });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      alert(data.detail || "Nie udało się usunąć ćwiczenia.");
      return;
    }
  } catch (err) {
    alert("Nie udało się połączyć z serwerem: " + err.message);
    return;
  }

  const scenarios = await (await fetch("/api/scenarios")).json();
  const wasActive = currentScenarioId === id;
  renderSidebar(scenarios, wasActive ? null : currentScenarioId);

  if (wasActive) {
    if (scenarios.length) {
      await selectScenario(scenarios[0].id);
    } else {
      selectSandbox();
    }
  }
}

function renderLessonsList(lessons, activeId) {
  const list = document.getElementById("lessons-list");
  if (!list) return;
  list.innerHTML = "";
  for (const lesson of lessons) {
    const composedId = LESSON_ID_PREFIX + lesson.id;
    const a = document.createElement("a");
    a.href = `/lessons/${lesson.id}`;
    a.className = "sidebar-item" + (composedId === activeId ? " active" : "");
    a.dataset.scenarioId = composedId;
    a.innerHTML = `<div class="sidebar-item-row"><span class="sidebar-item-title">${escapeHtml(lesson.title)}</span></div>`;
    a.addEventListener("click", (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      selectLesson(lesson.id);
    });
    list.appendChild(a);
  }
}

function renderIncidentsList(incidents, activeId) {
  const list = document.getElementById("incidents-list");
  if (!list) return;
  list.innerHTML = "";
  for (const incident of incidents) {
    const composedId = INCIDENT_ID_PREFIX + incident.id;
    const a = document.createElement("a");
    a.href = `/incidents/${incident.id}`;
    a.className = "sidebar-item" + (composedId === activeId ? " active" : "");
    a.dataset.scenarioId = composedId;
    a.innerHTML = `
      <div class="sidebar-item-row">
        <span class="sidebar-item-title">${escapeHtml(incident.title)}</span>
        <span class="badge incident-step-count">${incident.step_count} kroków</span>
      </div>
    `;
    a.addEventListener("click", (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      selectIncidentOverview(incident.id);
    });
    list.appendChild(a);
  }
}

function setSidebarActive(activeId) {
  // Queries the whole sidebar, not just #sidebar-list, so the pinned
  // "Wolne zapytania" sandbox link (a sibling of #sidebar-list, not part of
  // the dynamic scenario list) participates in the same active-state logic.
  for (const item of document.querySelectorAll(".sidebar .sidebar-item")) {
    item.classList.toggle("active", item.dataset.scenarioId === activeId);
  }
}

function wireInPlaceLinks(root) {
  root.querySelectorAll("[data-nav-id]").forEach((a) => {
    a.addEventListener("click", (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      selectScenario(a.dataset.navId);
    });
  });
}

function buildMainPanelShell() {
  const panel = document.getElementById("main-panel");
  panel.innerHTML = `
    <nav class="scenario-nav" id="scenario-nav"></nav>
    <div class="scenario-layout">
      <aside class="scenario-panel" id="scenario-info"></aside>
      <section class="editor-panel">
        <label for="kql-input" class="editor-label">Zapytanie KQL</label>
        <div class="editor-wrap">
          <pre class="editor-highlight" id="kql-highlight" aria-hidden="true"><code></code></pre>
          <textarea
            id="kql-input"
            class="editor-input"
            spellcheck="false"
            autocapitalize="off"
            autocomplete="off"
          ></textarea>
        </div>
        <div class="editor-actions">
          <button id="run-btn" class="btn btn-run">Uruchom</button>
          <span class="editor-hint-text">Ctrl/Cmd + Enter też uruchamia</span>
          <span id="run-status" class="run-status"></span>
        </div>
        <div class="check-target" id="check-target"></div>
        <div id="feedback" class="feedback" hidden></div>
        <div id="result-wrap" class="result-wrap" hidden>
          <h3>Wynik</h3>
          <div class="table-scroll">
            <table id="result-table"></table>
          </div>
        </div>
      </section>
    </div>
  `;
  setupEditor();
}

// Shared by renderScenarioInfo() (an "investigation" step, which is also a
// plain scenario page) and renderIncidentActionStep() (an "action" step) -
// both kinds of incident step get the same prev/next-step + "przegląd
// incydentu" nav.
function incidentNavHtml(ctx) {
  const prevHtml = ctx.prev_step
    ? `<a href="/incidents/${ctx.id}/steps/${ctx.prev_step}" data-incident-step="${ctx.prev_step}">&larr; poprzedni krok</a>`
    : "";
  const nextHtml = ctx.next_step
    ? `<a href="/incidents/${ctx.id}/steps/${ctx.next_step}" data-incident-step="${ctx.next_step}">następny krok &rarr;</a>`
    : "";
  return `
    <div class="scenario-nav-links">
      ${prevHtml}
      <a href="/incidents/${ctx.id}" data-incident-overview-link>przegląd scenariusza</a>
      ${nextHtml}
    </div>
  `;
}

function wireIncidentNavLinks(incidentId) {
  // Covers both the incident-crumb link (in #scenario-info) and the
  // prev/next-step + overview links (in #scenario-nav) in one pass.
  document.querySelectorAll("#main-panel [data-incident-step]").forEach((a) => {
    a.addEventListener("click", (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      selectIncidentStep(incidentId, parseInt(a.dataset.incidentStep, 10));
    });
  });
  document.querySelectorAll("#main-panel [data-incident-overview-link]").forEach((a) => {
    a.addEventListener("click", (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      selectIncidentOverview(incidentId);
    });
  });
}

function renderScenarioInfo(data) {
  currentScenarioId = data.id;
  currentScenarioTitle = data.title;
  currentScenarioSourceUrl = data.source_url || null;
  currentIncidentContext = data.incident || null;

  document.getElementById("check-target").innerHTML =
    `Sprawdzane względem: <strong>${escapeHtml(data.title)}</strong>`;
  document.getElementById("kql-input").placeholder = `${data.datasets[0] || ""} | where ...`;

  const hintHtml = data.hint
    ? `<details class="hint"><summary>Podpowiedź</summary><p>${escapeHtml(data.hint)}</p></details>`
    : "";
  const mitreHtml = data.mitre_techniques.length
    ? `<div class="mitre-tags">${mitreTagsHtml(data.mitre_techniques)}</div>`
    : "";
  const sc200Html = data.sc200_area
    ? `<span class="sc200-tag" title="Obszar SC-200">SC-200: ${escapeHtml(data.sc200_area)}</span>`
    : "";
  // When a scenario is opened as a step of an incident, data carries an
  // extra "incident" key (see app/incident_registry.py's get_incident_step_or_404) -
  // everything else about this function stays the plain-scenario path.
  const incidentBannerHtml = data.incident
    ? `
      <div class="incident-banner">
        <div class="incident-crumb">
          Scenariusz: <a href="/incidents/${data.incident.id}" data-incident-overview-link>${escapeHtml(data.incident.title)}</a>
          — krok ${data.incident.step_number} z ${data.incident.step_count}
        </div>
        <p class="incident-narrative">${escapeHtml(data.incident.narrative)}</p>
      </div>
    `
    : "";

  document.getElementById("scenario-info").innerHTML = `
    ${incidentBannerHtml}
    ${difficultyBadge(data)}
    ${sc200Html}
    <h1>${escapeHtml(data.title)}</h1>
    <p class="prompt">${escapeHtml(data.prompt)}</p>
    ${mitreHtml}
    <dl class="meta-list">
      <dt>Dataset(y)</dt>
      <dd>${escapeHtml(data.datasets.join(", "))}</dd>
    </dl>
    ${hintHtml}
    <details class="solution" id="solution-details">
      <summary>Pokaż rozwiązanie</summary>
      <div class="solution-body" id="solution-body"></div>
    </details>
  `;
  setupSolutionReveal(data.id);

  const nav = document.getElementById("scenario-nav");
  if (data.incident) {
    nav.innerHTML = incidentNavHtml(data.incident);
    wireIncidentNavLinks(data.incident.id);
  } else {
    const prevHtml = data.prev_id
      ? `<a href="/scenarios/${data.prev_id}" data-nav-id="${data.prev_id}">&larr; poprzedni</a>`
      : "";
    const nextHtml = data.next_id
      ? `<a href="/scenarios/${data.next_id}" data-nav-id="${data.next_id}">następny &rarr;</a>`
      : "";
    nav.innerHTML = `<div class="scenario-nav-links">${prevHtml}${nextHtml}</div>`;
    wireInPlaceLinks(nav);
  }
}

function renderSolutionBody(solution) {
  const body = document.getElementById("solution-body");
  if (!solution.reference_query) {
    body.innerHTML = `<p class="solution-message">${escapeHtml(solution.message || "Brak wzorcowego zapytania.")}</p>`;
    return;
  }
  body.innerHTML = `
    <pre class="solution-query"><code>${highlightKql(solution.reference_query)}</code></pre>
    <div class="table-scroll"><table class="solution-table"></table></div>
  `;
  renderDataTable(body.querySelector(".solution-table"), solution.columns, solution.rows);
}

function setupSolutionReveal(scenarioId) {
  const details = document.getElementById("solution-details");
  let loaded = false;
  details.addEventListener("toggle", async () => {
    if (!details.open || loaded) return;
    loaded = true;
    const body = document.getElementById("solution-body");
    body.innerHTML = `<p class="solution-message">Ładowanie...</p>`;
    try {
      const response = await fetch(`/api/scenarios/${scenarioId}/solution`);
      if (!response.ok) throw new Error(`serwer zwrócił ${response.status}`);
      renderSolutionBody(await response.json());
    } catch (err) {
      body.innerHTML = `<p class="solution-message">Nie udało się wczytać rozwiązania: ${escapeHtml(err.message)}</p>`;
      loaded = false;
    }
  });
}

async function renderSandboxInfo() {
  currentScenarioId = SANDBOX_ID;
  currentScenarioTitle = "Wolne zapytania";
  currentScenarioSourceUrl = null;

  document.getElementById("check-target").textContent = "Tryb eksploracji — bez oceniania.";
  document.getElementById("kql-input").placeholder = "TableName | where ...";
  document.getElementById("scenario-nav").innerHTML = "";

  document.getElementById("scenario-info").innerHTML = `
    <h1>Wolne zapytania</h1>
    <p class="prompt">Eksploruj cały wspólny zbiór logów bez oceniania - napisz dowolne zapytanie KQL.</p>
    <dl class="meta-list" id="sandbox-tables">
      <dt>Dostępne tabele</dt>
      <dd>Ładowanie...</dd>
    </dl>
  `;

  try {
    const response = await fetch("/api/tables");
    if (!response.ok) throw new Error(`serwer zwrócił ${response.status}`);
    const tables = await response.json();
    const dd = document.querySelector("#sandbox-tables dd");
    if (dd) dd.textContent = tables.map((t) => `${t.name} (${t.row_count})`).join(", ");
  } catch (err) {
    const dd = document.querySelector("#sandbox-tables dd");
    if (dd) dd.textContent = "Nie udało się wczytać listy tabel.";
  }
}

function renderLessonInfo(data) {
  currentScenarioId = LESSON_ID_PREFIX + data.id;
  currentScenarioTitle = data.title;
  currentScenarioSourceUrl = null;

  document.getElementById("check-target").textContent = "Tryb nauki — bez oceniania.";
  document.getElementById("kql-input").placeholder = "TableName | where ...";
  document.getElementById("scenario-nav").innerHTML = "";

  document.getElementById("scenario-info").innerHTML = `
    <h1>${escapeHtml(data.title)}</h1>
    <p class="prompt">${escapeHtml(data.description)}</p>
    <pre class="solution-query"><code>${highlightKql(data.example_query)}</code></pre>
    <p class="solution-message">${escapeHtml(data.example_explanation)}</p>
    <button type="button" class="btn btn-secondary" id="insert-example-btn">Wstaw przykład do edytora</button>
  `;

  document.getElementById("insert-example-btn").addEventListener("click", () => {
    const input = document.getElementById("kql-input");
    input.value = data.example_query;
    // Reuses setupEditor()'s own "input" listener (syntax-highlight refresh)
    // instead of calling it directly - deliberately does NOT run the query,
    // so "Uruchom" stays the one consistent way a query ever executes.
    input.dispatchEvent(new Event("input"));
    input.focus();
  });
}

function incidentStepRowHtml(incidentId, step) {
  if (step.kind === "action") {
    const done = isActionStepDone(incidentId, step.step_number, step.actions.length);
    const doneHtml = done ? `<span class="sidebar-item-solved" title="Wykonano">✓</span>` : "";
    return `
      <li class="incident-step" data-step-number="${step.step_number}">
        <div class="incident-step-row">
          <span class="incident-step-number">${step.step_number}.</span>
          <span class="incident-step-title">${escapeHtml(step.title)}</span>
          ${doneHtml}
          <span class="badge action-badge">Działanie IR</span>
        </div>
        <p class="incident-step-narrative">${escapeHtml(step.narrative)}</p>
      </li>
    `;
  }
  const solved = getSolvedIds().has(step.scenario_id);
  const solvedHtml = solved ? `<span class="sidebar-item-solved" title="Rozwiązano">✓</span>` : "";
  const mitreHtml = step.mitre_techniques.length ? mitreTagsHtml(step.mitre_techniques) : "";
  return `
    <li class="incident-step" data-step-number="${step.step_number}">
      <div class="incident-step-row">
        <span class="incident-step-number">${step.step_number}.</span>
        <span class="incident-step-title">${escapeHtml(step.scenario_title)}</span>
        ${solvedHtml}
        <span class="badge badge-${escapeHtml(step.difficulty)}">${escapeHtml(step.difficulty)}</span>
      </div>
      <p class="incident-step-narrative">${escapeHtml(step.narrative)}</p>
      ${mitreHtml ? `<div class="mitre-tags">${mitreHtml}</div>` : ""}
    </li>
  `;
}

function renderIncidentOverview(data) {
  currentScenarioId = INCIDENT_ID_PREFIX + data.id;
  currentScenarioTitle = data.title;
  currentScenarioSourceUrl = null;
  currentIncidentContext = null;

  document.getElementById("check-target").textContent = "Przegląd scenariusza — wybierz krok, aby rozpocząć.";
  document.getElementById("kql-input").placeholder = "TableName | where ...";
  document.getElementById("scenario-nav").innerHTML = "";

  document.getElementById("scenario-info").innerHTML = `
    <h1>${escapeHtml(data.title)}</h1>
    <p class="prompt">${escapeHtml(data.summary)}</p>
    <ol class="incident-steps">${data.steps.map((step) => incidentStepRowHtml(data.id, step)).join("")}</ol>
  `;

  document.querySelectorAll("#scenario-info .incident-step").forEach((li) => {
    li.addEventListener("click", () => {
      selectIncidentStep(data.id, parseInt(li.dataset.stepNumber, 10));
    });
  });
}

function renderIncidentActionStep(data) {
  // No real scenario behind an action step - currentScenarioId is a
  // synthetic, incident-prefixed id so runQuery()'s isUngraded check treats
  // it like the sandbox (the persistent editor still works as a free-query
  // tool, it just never grades against anything here).
  currentScenarioId = INCIDENT_ID_PREFIX + data.id;
  currentScenarioTitle = data.title;
  currentScenarioSourceUrl = null;
  currentIncidentContext = data.incident;

  document.getElementById("check-target").textContent = "Krok proceduralny — bez oceniania KQL.";
  document.getElementById("kql-input").placeholder = "TableName | where ...";

  const incidentBannerHtml = `
    <div class="incident-banner">
      <div class="incident-crumb">
        Scenariusz: <a href="/incidents/${data.incident.id}" data-incident-overview-link>${escapeHtml(data.incident.title)}</a>
        — krok ${data.incident.step_number} z ${data.incident.step_count}
      </div>
    </div>
  `;

  const actionsHtml = data.actions
    .map((action, i) => {
      const checked = isActionChecked(data.incident.id, data.incident.step_number, i);
      return `
        <li class="action-item">
          <label>
            <input type="checkbox" class="action-checkbox" data-action-index="${i}" ${checked ? "checked" : ""}>
            <span>${escapeHtml(action)}</span>
          </label>
        </li>
      `;
    })
    .join("");

  document.getElementById("scenario-info").innerHTML = `
    ${incidentBannerHtml}
    <span class="badge action-badge">Działanie IR</span>
    <h1>${escapeHtml(data.title)}</h1>
    <p class="prompt">${escapeHtml(data.incident.narrative)}</p>
    <ul class="action-checklist">${actionsHtml}</ul>
  `;

  document.querySelectorAll("#scenario-info .action-checkbox").forEach((cb) => {
    cb.addEventListener("change", () => {
      toggleActionChecked(data.incident.id, data.incident.step_number, parseInt(cb.dataset.actionIndex, 10));
    });
  });

  document.getElementById("scenario-nav").innerHTML = incidentNavHtml(data.incident);
  wireIncidentNavLinks(data.incident.id);
}

function setupEditor() {
  const input = document.getElementById("kql-input");
  const highlightPre = document.getElementById("kql-highlight");
  const highlightCode = highlightPre.querySelector("code");
  const runBtn = document.getElementById("run-btn");
  const runStatus = document.getElementById("run-status");
  const feedback = document.getElementById("feedback");
  const resultWrap = document.getElementById("result-wrap");
  const resultTable = document.getElementById("result-table");

  function refreshHighlight() {
    // Trailing newline keeps the last line's height from collapsing when
    // the textarea's own value ends in one.
    highlightCode.innerHTML = highlightKql(input.value) + "\n";
  }

  function syncScroll() {
    highlightPre.scrollTop = input.scrollTop;
    highlightPre.scrollLeft = input.scrollLeft;
  }

  input.addEventListener("input", refreshHighlight);
  input.addEventListener("scroll", syncScroll);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Tab") {
      event.preventDefault();
      const start = input.selectionStart;
      const end = input.selectionEnd;
      input.value = input.value.slice(0, start) + "  " + input.value.slice(end);
      input.selectionStart = input.selectionEnd = start + 2;
      refreshHighlight();
    } else if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      runBtn.click();
    }
  });
  refreshHighlight();

  function showFeedback(correct, message, sourceUrl) {
    feedback.hidden = false;
    // correct === null is the sandbox's neutral "query ran fine, nothing to
    // grade" state - distinct from the green/red correct/incorrect states.
    const cls = correct === null ? "feedback-neutral" : correct ? "feedback-correct" : "feedback-incorrect";
    feedback.className = "feedback " + cls;

    feedback.textContent = "";
    feedback.appendChild(document.createTextNode(message));
    // The source writeup is only revealed on a correct answer - it's a
    // "read the real incident" reward, not something to spoil the exercise
    // with up front. Built via DOM APIs (not innerHTML) since sourceUrl
    // ultimately comes from scenario JSON data, not a trusted constant.
    if (correct === true && sourceUrl) {
      feedback.appendChild(document.createElement("br"));
      const link = document.createElement("a");
      link.href = sourceUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.className = "feedback-source-link";
      link.textContent = "📖 Przeczytaj oryginalny writeup";
      feedback.appendChild(link);
    }
  }

  function renderTable(columns, rows) {
    if (!columns.length) {
      resultTable.innerHTML = "";
      resultWrap.hidden = true;
      return;
    }
    resultWrap.hidden = false;
    renderDataTable(resultTable, columns, rows);
  }

  async function runQuery() {
    const query = input.value.trim();
    if (!query) return;

    // Read at click time, not captured once at setup: setupEditor() only
    // runs once, but which scenario "Uruchom" grades against (or whether
    // it's ungraded - sandbox or a lesson) can change on every sidebar click.
    const scenarioId = currentScenarioId;
    const isUngraded =
      scenarioId === SANDBOX_ID ||
      scenarioId.startsWith(LESSON_ID_PREFIX) ||
      scenarioId.startsWith(INCIDENT_ID_PREFIX);

    runBtn.disabled = true;
    runStatus.textContent = "Uruchamianie...";
    feedback.hidden = true;
    resultWrap.hidden = true;

    try {
      const url = isUngraded ? "/api/query" : `/api/scenarios/${scenarioId}/run`;
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await response.json();

      if (!response.ok) {
        showFeedback(false, data.detail || "Błąd serwera.");
        return;
      }

      if (isUngraded) {
        if (data.error) {
          showFeedback(false, data.error);
        } else {
          showFeedback(null, `Zwrócono ${data.rows.length} wiersz(y).`);
        }
      } else {
        showFeedback(data.correct, data.error || data.message, currentScenarioSourceUrl);
        if (data.correct) markSolved(scenarioId);
      }
      if (!data.error) {
        renderTable(data.columns, data.rows);
      }
    } catch (err) {
      showFeedback(false, "Nie udało się połączyć z serwerem: " + err.message);
    } finally {
      runBtn.disabled = false;
      runStatus.textContent = "";
    }
  }

  runBtn.addEventListener("click", runQuery);
}

async function selectScenario(id, { push = true } = {}) {
  // Also re-renders if the id matches but we're currently showing it as an
  // incident step - clicking the plain scenario link should drop the
  // incident banner/nav, not no-op.
  if (id === currentScenarioId && !currentIncidentContext) return;
  try {
    const response = await fetch(`/api/scenarios/${id}`);
    if (!response.ok) throw new Error(`serwer zwrócił ${response.status}`);
    const data = await response.json();

    renderScenarioInfo(data);
    setSidebarActive(data.id);
    document.title = `${data.title} - Blue Team Simulator`;
    if (push) history.pushState({ id: data.id }, "", `/scenarios/${data.id}`);
  } catch (err) {
    console.error("Nie udało się wczytać scenariusza:", err);
  }
}

function selectSandbox({ push = true } = {}) {
  if (currentScenarioId === SANDBOX_ID) return;
  renderSandboxInfo();
  setSidebarActive(SANDBOX_ID);
  document.title = "Wolne zapytania - Blue Team Simulator";
  if (push) history.pushState({ id: SANDBOX_ID }, "", "/sandbox");
}

async function selectLesson(id, { push = true } = {}) {
  const composedId = LESSON_ID_PREFIX + id;
  if (composedId === currentScenarioId) return;
  try {
    const response = await fetch(`/api/lessons/${id}`);
    if (!response.ok) throw new Error(`serwer zwrócił ${response.status}`);
    const data = await response.json();

    renderLessonInfo(data);
    setSidebarActive(composedId);
    document.title = `${data.title} - Blue Team Simulator`;
    if (push) history.pushState({ id: composedId }, "", `/lessons/${id}`);
  } catch (err) {
    console.error("Nie udało się wczytać lekcji:", err);
  }
}

async function selectIncidentOverview(id, { push = true } = {}) {
  const composedId = INCIDENT_ID_PREFIX + id;
  if (composedId === currentScenarioId) return;
  try {
    const response = await fetch(`/api/incidents/${id}`);
    if (!response.ok) throw new Error(`serwer zwrócił ${response.status}`);
    const data = await response.json();

    renderIncidentOverview(data);
    setSidebarActive(composedId);
    document.title = `${data.title} - Blue Team Simulator`;
    if (push) history.pushState({ id: composedId }, "", `/incidents/${id}`);
  } catch (err) {
    console.error("Nie udało się wczytać incydentu:", err);
  }
}

async function selectIncidentStep(incidentId, stepNumber, { push = true } = {}) {
  try {
    const response = await fetch(`/api/incidents/${incidentId}/steps/${stepNumber}`);
    if (!response.ok) throw new Error(`serwer zwrócił ${response.status}`);
    const data = await response.json();

    const isAction = data.kind === "action";
    if (isAction) {
      renderIncidentActionStep(data);
    } else {
      // Reuses the exact same renderer as a plain scenario page - the extra
      // data.incident key is what makes it show the incident banner/nav.
      renderScenarioInfo(data);
    }
    setSidebarActive(isAction ? INCIDENT_ID_PREFIX + incidentId : data.id);
    document.title = `${data.title} - Blue Team Simulator`;
    if (push) {
      history.pushState(
        { id: isAction ? INCIDENT_ID_PREFIX + data.id : data.id, incident: { id: incidentId, step: stepNumber } },
        "",
        `/incidents/${incidentId}/steps/${stepNumber}`
      );
    }
  } catch (err) {
    console.error("Nie udało się wczytać kroku incydentu:", err);
  }
}

function showImportFeedback(success, message) {
  const el = document.getElementById("import-feedback");
  el.hidden = false;
  el.textContent = message;
  el.className = "import-feedback " + (success ? "import-feedback-success" : "import-feedback-error");
}

function setupImport() {
  const importBtn = document.getElementById("import-btn");
  const fileInput = document.getElementById("import-file-input");

  importBtn.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    fileInput.value = "";
    if (!file) return;

    importBtn.disabled = true;
    try {
      const text = await file.text();
      const response = await fetch("/api/scenarios/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: text,
      });
      const data = await response.json();

      if (!response.ok) {
        showImportFeedback(false, data.detail || "Błąd importu.");
        return;
      }

      showImportFeedback(true, `Zaimportowano ćwiczenie: ${data.scenario.title}`);

      const listResponse = await fetch("/api/scenarios");
      const scenarios = await listResponse.json();
      renderSidebar(scenarios, data.scenario.id);
      renderScenarioInfo(data.scenario);
      document.title = `${data.scenario.title} - Blue Team Simulator`;
      history.pushState({ id: data.scenario.id }, "", `/scenarios/${data.scenario.id}`);
    } catch (err) {
      showImportFeedback(false, "Nie udało się połączyć z serwerem: " + err.message);
    } finally {
      importBtn.disabled = false;
    }
  });
}

// Sidebar width is user-adjustable (drag the handle between sidebar and main
// panel) and persisted in localStorage so it survives reloads - purely a
// client-side preference, no server state.
const SIDEBAR_WIDTH_KEY = "btsim_sidebar_width";
const SIDEBAR_DEFAULT_WIDTH = 280;
const SIDEBAR_MIN_WIDTH = 200;
const SIDEBAR_MAX_WIDTH = 480;

function applySidebarWidth(px) {
  document.documentElement.style.setProperty("--sidebar-width", `${px}px`);
}

function loadSidebarWidth() {
  const stored = parseInt(localStorage.getItem(SIDEBAR_WIDTH_KEY), 10);
  if (!Number.isNaN(stored)) {
    applySidebarWidth(Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, stored)));
  }
}

function setupSidebarResize() {
  const handle = document.getElementById("sidebar-resize");
  const shell = document.querySelector(".app-shell");
  if (!handle || !shell) return;

  let dragging = false;

  function onPointerMove(event) {
    if (!dragging) return;
    const rect = shell.getBoundingClientRect();
    const width = Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, event.clientX - rect.left));
    applySidebarWidth(width);
  }

  function onPointerUp() {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove("dragging");
    document.body.classList.remove("resizing-sidebar");
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
    const current = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--sidebar-width"), 10);
    if (!Number.isNaN(current)) {
      try {
        localStorage.setItem(SIDEBAR_WIDTH_KEY, String(current));
      } catch (err) {
        // localStorage unavailable - the width just won't survive a reload
      }
    }
  }

  handle.addEventListener("pointerdown", (event) => {
    dragging = true;
    handle.classList.add("dragging");
    document.body.classList.add("resizing-sidebar");
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    event.preventDefault();
  });

  handle.addEventListener("dblclick", () => {
    applySidebarWidth(SIDEBAR_DEFAULT_WIDTH);
    try {
      localStorage.removeItem(SIDEBAR_WIDTH_KEY);
    } catch (err) {
      // ignore
    }
  });
}

function init() {
  const scenariosBlob = document.getElementById("scenarios-data");
  const lessonsBlob = document.getElementById("lessons-data");
  const incidentsBlob = document.getElementById("incidents-data");
  const initialBlob = document.getElementById("initial-scenario-data");
  if (!scenariosBlob || !initialBlob) return; // not the shell page

  const scenarios = JSON.parse(scenariosBlob.textContent);
  const lessons = lessonsBlob ? JSON.parse(lessonsBlob.textContent) : [];
  const incidents = incidentsBlob ? JSON.parse(incidentsBlob.textContent) : [];
  const initial = JSON.parse(initialBlob.textContent);

  loadSidebarWidth();
  setupSidebarResize();
  buildMainPanelShell();
  renderSidebar(scenarios, initial.id);
  renderLessonsList(lessons, initial.id);
  renderIncidentsList(incidents, initial.id);
  if (initial.kind === "action") {
    // A direct-linked incident action-step page: initial.id is a synthetic
    // "incidentId:step:n" id (bare, not "incident:"-prefixed), so it can't
    // be told apart from other pseudo ids by .startsWith like the branches
    // below - the "kind" field is what discriminates it, and it must be
    // checked before any of them.
    renderIncidentActionStep(initial);
  } else if (initial.id === SANDBOX_ID) {
    renderSandboxInfo();
  } else if (initial.id.startsWith(LESSON_ID_PREFIX)) {
    renderLessonInfo(initial.lesson);
  } else if (initial.id.startsWith(INCIDENT_ID_PREFIX)) {
    renderIncidentOverview(initial.incident);
  } else {
    // Covers both a plain scenario page and an incident investigation *step*
    // page - a step page's initial.id is the real scenario id, with an
    // extra initial.incident key that renderScenarioInfo itself checks for.
    renderScenarioInfo(initial);
  }
  setSidebarActive(initial.kind === "action" ? INCIDENT_ID_PREFIX + initial.incident.id : initial.id);
  if (initial.kind === "action") {
    history.replaceState(
      { id: currentScenarioId, incident: { id: initial.incident.id, step: initial.incident.step_number } },
      "",
      location.pathname
    );
  } else {
    history.replaceState({ id: initial.id }, "", location.pathname);
  }

  window.addEventListener("popstate", (event) => {
    if (!event.state || !event.state.id) return;
    if (event.state.incident) {
      selectIncidentStep(event.state.incident.id, event.state.incident.step, { push: false });
    } else if (event.state.id === SANDBOX_ID) {
      selectSandbox({ push: false });
    } else if (event.state.id.startsWith(LESSON_ID_PREFIX)) {
      selectLesson(event.state.id.slice(LESSON_ID_PREFIX.length), { push: false });
    } else if (event.state.id.startsWith(INCIDENT_ID_PREFIX)) {
      selectIncidentOverview(event.state.id.slice(INCIDENT_ID_PREFIX.length), { push: false });
    } else {
      selectScenario(event.state.id, { push: false });
    }
  });

  const sandboxLink = document.getElementById("sandbox-link");
  sandboxLink.addEventListener("click", (event) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    selectSandbox();
  });

  setupImport();
}

document.addEventListener("DOMContentLoaded", init);
