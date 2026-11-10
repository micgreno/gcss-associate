const main = document.getElementById("database-content");
const pageParams = new URLSearchParams(window.location.search);
const userId = pageParams.get("as_user") || "superuser";
const requestedReturnTo = pageParams.get("return_to") || "/";
let returnTo = "/";
try {
  const candidateReturnUrl = new URL(requestedReturnTo, window.location.origin);
  if (candidateReturnUrl.origin === window.location.origin) {
    returnTo = `${candidateReturnUrl.pathname}${candidateReturnUrl.search}${candidateReturnUrl.hash}`;
  }
} catch { /* Keep the safe borrower-list fallback. */ }
const selectedTables = [];
const selectedColumns = new Set();
const joinState = new Map();
let schema = [];
let joinTypes = [];
let filters = [];
let orderBy = [];
let lastResult = null;

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
})[character]);
const keyOf = (table, column) => JSON.stringify([table, column]);
const splitKey = (key) => {
  try { const [table, column] = JSON.parse(key); return { table, column }; }
  catch { return { table: "", column: "" }; }
};
const tableMeta = (name) => schema.find((table) => table.name === name);
const allCanvasFields = () => selectedTables.flatMap((table) => tableMeta(table).columns.map((column) => ({ table, column: column.name })));

function urlFor(path, user = userId) {
  const url = new URL(path, window.location.origin);
  url.searchParams.set("as_user", user);
  return `${url.pathname}${url.search}`;
}

async function getJson(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "The request failed.");
  return payload;
}

async function postJson(payload) {
  const response = await fetch(urlFor("/api/database/query"), {
    method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "The query failed.");
  return result;
}

function setHeader(session) {
  const selector = document.getElementById("as-user");
  selector.innerHTML = session.users.map((user) =>
    `<option value="${esc(user.userId)}"${user.userId === session.userId ? " selected" : ""}>${esc(user.displayName)}</option>`
  ).join("");
  document.getElementById("brand-link").href = urlFor("/");
  const databaseLink = document.getElementById("database-link");
  databaseLink.hidden = false;
  databaseLink.href = urlFor("/database", session.userId);
  const returnLink = document.getElementById("return-link");
  const returnUrl = new URL(returnTo, window.location.origin);
  returnUrl.searchParams.set("as_user", session.userId);
  returnLink.href = `${returnUrl.pathname}${returnUrl.search}${returnUrl.hash}`;
  document.getElementById("role-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const nextUser = selector.value;
    const target = new URL(urlFor("/database", nextUser), window.location.origin);
    if (returnTo !== "/") target.searchParams.set("return_to", returnTo);
    window.location.assign(`${target.pathname}${target.search}`);
  }, { once: true });
}

function setStatus(message, kind = "muted") {
  const target = document.getElementById("query-status");
  target.className = kind;
  target.textContent = message;
}

function clearResults(message = "Choose a table or run a query.") {
  lastResult = null;
  document.getElementById("result-actions").hidden = true;
  document.getElementById("query-results").replaceChildren();
  setStatus(message);
}

function renderResults(result) {
  const host = document.getElementById("query-results");
  lastResult = result;
  if (!result.columns.length) {
    host.textContent = "The query returned no columns.";
    setStatus("The query returned no columns.", "error");
    return;
  }
  const table = document.createElement("table");
  table.className = "result-table";
  table.innerHTML = `<thead><tr>${result.columns.map((column) => `<th>${esc(column)}</th>`).join("")}</tr></thead><tbody>${result.rows.map((row) => `<tr>${row.map((value) => `<td>${esc(value === null ? "NULL" : value)}</td>`).join("")}</tr>`).join("")}</tbody>`;
  const wrapper = document.createElement("div");
  wrapper.className = "query-results";
  wrapper.append(table);
  host.replaceChildren(wrapper);
  document.getElementById("result-actions").hidden = false;
  setStatus(`${result.rows.length}${result.truncated ? " or more" : ""} row${result.rows.length === 1 ? "" : "s"} returned${result.truncated ? ` (limited to ${result.rowLimit})` : ""}.`, "success");
}

function tabularText(rows) {
  return rows.map((row) => row.map((value) => String(value ?? "").replace(/[\t\r\n]+/g, " ")).join("\t")).join("\r\n");
}

async function copyResults() {
  if (!lastResult?.columns?.length) return;
  const content = tabularText([lastResult.columns, ...lastResult.rows]);
  try {
    await navigator.clipboard.writeText(content);
  } catch {
    const helper = document.createElement("textarea");
    helper.value = content;
    helper.setAttribute("aria-hidden", "true");
    helper.style.position = "fixed";
    helper.style.opacity = "0";
    document.body.append(helper);
    helper.select();
    const copied = document.execCommand("copy");
    helper.remove();
    if (!copied) { setStatus("Clipboard access was unavailable. You can still export the result as CSV.", "error"); return; }
  }
  setStatus(`Copied ${lastResult.rows.length} row${lastResult.rows.length === 1 ? "" : "s"} with headers. Paste into Excel or another spreadsheet.`, "success");
}

function exportResultsCsv() {
  if (!lastResult?.columns?.length) return;
  const csvCell = (value) => {
    const text = String(value ?? "");
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const csv = [lastResult.columns, ...lastResult.rows].map((row) => row.map(csvCell).join(",")).join("\r\n");
  const blob = new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" });
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const timestamp = new Date().toISOString().replace(/[:T]/g, "-").slice(0, 16);
  link.href = objectUrl;
  link.download = `database-query-${timestamp}.csv`;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  setStatus(`Exported ${lastResult.rows.length} row${lastResult.rows.length === 1 ? "" : "s"} with headers as CSV.`, "success");
}

function drawCatalog() {
  const host = document.getElementById("table-list");
  const query = document.getElementById("table-search")?.value.trim().toLocaleLowerCase() || "";
  const filtered = schema.filter((table) => `${table.name} ${table.columns.map((column) => column.name).join(" ")}`.toLocaleLowerCase().includes(query));
  host.innerHTML = filtered.map((table) => `<details class="table-card" draggable="true" data-table="${esc(table.name)}">
    <summary><strong>${esc(table.name)}</strong> <span class="muted">· ${table.columns.length} columns</span></summary>
    <ul>${table.columns.map((column) => `<li>${esc(column.name)}${column.pk ? " · primary key" : ""}</li>`).join("")}</ul>
    <button type="button" class="catalog-action" data-add-table="${esc(table.name)}">Add to canvas</button></details>`).join("") || `<p class="muted">No tables or columns match that search.</p>`;
}

function renderSelectAll() {
  const allFields = allCanvasFields();
  const control = document.getElementById("select-all-wrap");
  const checkbox = document.getElementById("select-all-columns");
  control.hidden = allFields.length === 0;
  const selected = allFields.filter((field) => selectedColumns.has(keyOf(field.table, field.column))).length;
  checkbox.checked = allFields.length > 0 && selected === allFields.length;
  checkbox.indeterminate = selected > 0 && selected < allFields.length;
  control.querySelector("span").textContent = checkbox.checked ? "Deselect all columns" : "Select all columns";
}

function optionsForColumns(table, selected = "") {
  const columns = tableMeta(table)?.columns || [];
  return `<option value="" disabled${selected ? "" : " selected"}>Choose column</option>${columns.map((column) => `<option value="${esc(column.name)}"${column.name === selected ? " selected" : ""}>${esc(column.name)}</option>`).join("")}`;
}

function renderJoins() {
  const host = document.getElementById("join-config");
  if (selectedTables.length < 2) { host.replaceChildren(); return; }
  host.innerHTML = `<h3>Choose each join explicitly</h3><p class="muted">For each table after the first, choose the join type, an existing table, and the matching column on each side. The builder will not guess these choices.</p>`
    + selectedTables.slice(1).map((table, index) => {
      const state = joinState.get(table) || { joinType: "", leftTable: "", leftColumn: "", rightColumn: "" };
      const priorTables = selectedTables.slice(0, index + 1);
      const leftColumns = state.leftTable && priorTables.includes(state.leftTable) ? state.leftTable : "";
      return `<div class="join-row" data-join-table="${esc(table)}">
        <strong>Join ${esc(table)}:</strong>
        <label>Type <select class="join-type"><option value="" disabled${state.joinType ? "" : " selected"}>Choose join type</option>${joinTypes.map((type) => `<option value="${esc(type)}"${type === state.joinType ? " selected" : ""}>${esc(type)}</option>`).join("")}</select></label>
        <label>Existing table <select class="join-left-table"><option value="" disabled${leftColumns ? "" : " selected"}>Choose table</option>${priorTables.map((name) => `<option value="${esc(name)}"${name === leftColumns ? " selected" : ""}>${esc(name)}</option>`).join("")}</select></label>
        <label>Column from existing table <select class="join-left-column"${leftColumns ? "" : " disabled"}>${leftColumns ? optionsForColumns(leftColumns, state.leftColumn) : `<option value="" selected disabled>Choose column</option>`}</select></label>
        <span>equals</span>
        <label>Column from ${esc(table)} <select class="join-right-column">${optionsForColumns(table, state.rightColumn)}</select></label>
      </div>`;
    }).join("");
  host.querySelectorAll(".join-row").forEach((row) => {
    const table = row.dataset.joinTable;
    const state = joinState.get(table) || { joinType: "", leftTable: "", leftColumn: "", rightColumn: "" };
    row.querySelector(".join-type").addEventListener("change", (event) => { state.joinType = event.target.value; joinState.set(table, state); });
    row.querySelector(".join-left-table").addEventListener("change", (event) => {
      state.leftTable = event.target.value; state.leftColumn = ""; joinState.set(table, state); renderJoins();
    });
    row.querySelector(".join-left-column").addEventListener("change", (event) => { state.leftColumn = event.target.value; joinState.set(table, state); });
    row.querySelector(".join-right-column").addEventListener("change", (event) => { state.rightColumn = event.target.value; joinState.set(table, state); });
  });
}

function renderCanvas() {
  const canvas = document.getElementById("query-canvas");
  canvas.innerHTML = selectedTables.length ? selectedTables.map((name) => {
    const table = tableMeta(name);
    return `<article class="canvas-table"><div class="canvas-head"><strong>${esc(name)}</strong><button type="button" data-remove-table="${esc(name)}" aria-label="Remove ${esc(name)}">Remove</button></div>
      <div>${table.columns.map((column) => {
        const checked = selectedColumns.has(keyOf(name, column.name));
        return `<label class="field-option"><input class="field-check" type="checkbox" data-table="${esc(name)}" data-column="${esc(column.name)}"${checked ? " checked" : ""}>${esc(column.name)}</label>`;
      }).join("")}</div></article>`;
  }).join("") : "Drop tables here, or open Tables and choose Add to canvas.";
  canvas.classList.remove("drag-over");
  renderJoins();
  renderSelectAll();
  renderRules();
}

function fieldOptions(selected) {
  const fields = allCanvasFields();
  return `<option value="" disabled${selected ? "" : " selected"}>Choose column</option>${fields.map(({ table, column }) => {
    const key = keyOf(table, column);
    return `<option value="${esc(key)}"${key === selected ? " selected" : ""}>${esc(table)}.${esc(column)}</option>`;
  }).join("")}`;
}

function renderRules() {
  const host = document.getElementById("query-rules");
  host.innerHTML = `<h3>Filters</h3><div id="filter-list"></div><button type="button" id="add-filter" class="secondary">Add filter</button>
    <h3>Sort</h3><div id="sort-list"></div><button type="button" id="add-sort" class="secondary">Add sort</button>`;
  const filterList = document.getElementById("filter-list");
  filters.forEach((filter, index) => {
    const row = document.createElement("div"); row.className = "filter-row";
    row.innerHTML = `<select class="filter-field" aria-label="Filter column">${fieldOptions(filter.field)}</select>
      <select class="filter-operator" aria-label="Filter operation">${[
        ["=", "equals"], ["!=", "not equals"], ["contains", "contains"], [">", "greater than"], [">=", "greater or equal"], ["<", "less than"], ["<=", "less or equal"], ["is empty", "is empty"], ["is not empty", "is not empty"]
      ].map(([value, label]) => `<option value="${value}"${filter.operator === value ? " selected" : ""}>${label}</option>`).join("")}</select>
      <input class="filter-value" aria-label="Filter value" value="${esc(filter.value)}"${["is empty", "is not empty"].includes(filter.operator) ? " disabled" : ""}>
      <button type="button" class="secondary" data-remove-filter="${index}">Remove</button>`;
    filterList.append(row);
  });
  const sortList = document.getElementById("sort-list");
  orderBy.forEach((rule, index) => {
    const row = document.createElement("div"); row.className = "filter-row";
    row.innerHTML = `<select class="sort-field" aria-label="Sort column">${fieldOptions(rule.field)}</select>
      <select class="sort-direction" aria-label="Sort direction"><option${rule.direction === "ASC" ? " selected" : ""}>ASC</option><option${rule.direction === "DESC" ? " selected" : ""}>DESC</option></select>
      <button type="button" class="secondary" data-remove-sort="${index}">Remove</button>`;
    sortList.append(row);
  });
  host.onclick = (event) => {
    if (event.target.id === "add-filter") { filters.push({ field: "", operator: "=", value: "" }); renderRules(); }
    if (event.target.id === "add-sort") { orderBy.push({ field: "", direction: "ASC" }); renderRules(); }
    if (event.target.dataset.removeFilter !== undefined) { filters.splice(Number(event.target.dataset.removeFilter), 1); renderRules(); }
    if (event.target.dataset.removeSort !== undefined) { orderBy.splice(Number(event.target.dataset.removeSort), 1); renderRules(); }
  };
  host.onchange = (event) => {
    const row = event.target.closest(".filter-row"); if (!row) return;
    const list = row.closest("#filter-list") ? filters : orderBy;
    const index = Array.from(row.parentElement.children).indexOf(row);
    if (event.target.matches(".filter-field")) list[index].field = event.target.value;
    if (event.target.matches(".filter-operator")) { list[index].operator = event.target.value; renderRules(); }
    if (event.target.matches(".sort-field")) list[index].field = event.target.value;
    if (event.target.matches(".sort-direction")) list[index].direction = event.target.value;
  };
  host.oninput = (event) => {
    if (!event.target.matches(".filter-value")) return;
    const row = event.target.closest(".filter-row");
    const index = Array.from(row.parentElement.children).indexOf(row);
    filters[index].value = event.target.value;
  };
}

function visualSpec() {
  const joins = selectedTables.slice(1).map((table) => ({ table, ...(joinState.get(table) || {}) }));
  const columns = Array.from(selectedColumns, (key) => splitKey(key));
  return {
    tables: [...selectedTables], joins, columns,
    filters: filters.map((filter) => ({ ...splitKey(filter.field), operator: filter.operator, value: filter.value })),
    order: orderBy.map((rule) => ({ ...splitKey(rule.field), direction: rule.direction })),
  };
}

function clearVisual() {
  selectedTables.splice(0);
  selectedColumns.clear();
  joinState.clear();
  filters = [];
  orderBy = [];
  renderCanvas();
  document.getElementById("generated-sql").textContent = "Build a visual query to see its SQL.";
  clearResults();
}

function addTable(name) {
  if (!tableMeta(name) || selectedTables.includes(name)) return;
  selectedTables.push(name);
  if (selectedTables.length > 1 && !joinState.has(name)) {
    joinState.set(name, { joinType: "", leftTable: "", leftColumn: "", rightColumn: "" });
  }
  renderCanvas();
}

function removeTable(name) {
  const index = selectedTables.indexOf(name);
  if (index < 0) return;
  selectedTables.splice(index, 1);
  for (const field of Array.from(selectedColumns)) if (splitKey(field).table === name) selectedColumns.delete(field);
  joinState.delete(name);
  for (const [table, state] of joinState) {
    if (state.leftTable === name) joinState.set(table, { ...state, leftTable: "", leftColumn: "" });
  }
  filters = filters.filter((rule) => !rule.field || selectedTables.includes(splitKey(rule.field).table));
  orderBy = orderBy.filter((rule) => !rule.field || selectedTables.includes(splitKey(rule.field).table));
  renderCanvas();
}

async function runQuery(payload, generatedSql = false) {
  const results = document.getElementById("query-results");
  clearResults("Running query…");
  if (generatedSql) document.getElementById("generated-sql").textContent = "Generating SQL…";
  try {
    const result = await postJson(payload);
    if (generatedSql) document.getElementById("generated-sql").textContent = result.generatedSql;
    renderResults(result);
  } catch (error) {
    results.replaceChildren();
    if (generatedSql) document.getElementById("generated-sql").textContent = "Query failed; SQL was not generated.";
    setStatus(error.message, "error");
  }
}

function chooseMode(mode) {
  const visual = mode === "visual";
  document.getElementById("visual-mode").hidden = !visual;
  document.getElementById("sql-mode").hidden = visual;
  document.getElementById("visual-mode-tab").setAttribute("aria-pressed", String(visual));
  document.getElementById("sql-mode-tab").setAttribute("aria-pressed", String(!visual));
  document.getElementById("catalog-help").textContent = visual
    ? "Review the tables and columns, or add a table to the visual builder."
    : "Data dictionary: expand a table to review available columns for your SQL statement.";
  document.querySelectorAll(".catalog-action").forEach((button) => { button.hidden = !visual; });
}

function renderUtility() {
  main.innerHTML = `<section class="eyebrow">Data tools</section><h1>Database utility</h1>
    <p class="muted">Browse this app's local synthetic SQLite database. Queries run read-only and return up to 250 rows.</p>
    <details class="card" open><summary>How to use this utility</summary><ol>
      <li>Choose <strong>Visual query builder</strong> to assemble a query by dragging tables to the canvas, or choose <strong>Write SQL</strong> to enter a SELECT statement yourself. The tables and columns catalog is available in either mode.</li>
      <li>In the visual builder, select the columns to return. Use <strong>Select all columns</strong> to include every column on the canvas. For each additional table, choose the join type and both matching columns. The utility does not infer joins.</li>
      <li>Add filters or sorting, run the query, and review its results below. Copy results with headers for a spreadsheet or download them as CSV. Queries are read-only and limited to 250 rows.</li>
    </ol></details>
    <div class="query-grid">
      <details class="card catalog"><summary><strong>Tables and columns</strong> <span class="muted">(expand as a data dictionary)</span></summary><p id="catalog-help" class="muted">Review the tables and columns, or add a table to the visual builder.</p><input id="table-search" class="search-box" type="search" placeholder="Search tables and columns" aria-label="Search database tables and columns"><div id="table-list" class="table-list">Loading tables…</div></details>
      <div class="mode-panel"><div class="mode-tabs" role="group" aria-label="Database query method"><button type="button" id="visual-mode-tab" aria-pressed="true">Visual query builder</button><button type="button" id="sql-mode-tab" aria-pressed="false">Write SQL</button></div>
      <section id="visual-mode" class="query-mode"><section class="card workbench"><h2>Visual query builder</h2><div id="query-canvas" class="query-canvas">Drop tables here, or open Tables and choose Add to canvas.</div>
        <label id="select-all-wrap" class="bulk-select" hidden><input id="select-all-columns" type="checkbox"> <span>Select all columns</span></label>
        <div id="join-config"></div><div id="query-rules"></div>
        <div class="actions"><button id="run-visual" type="button">Run visual query</button><button id="clear-visual" type="button" class="secondary">Clear</button></div>
        <details><summary>Generated SQL</summary><pre id="generated-sql">Build a visual query to see its SQL.</pre></details>
      </section>
      </section>
      <section id="sql-mode" class="query-mode" hidden><div class="card"><h2>Write SQL</h2><p class="muted">Write a SELECT statement yourself. Writes and schema changes are blocked.</p>
      <textarea id="sql-input" rows="7" spellcheck="false" aria-label="SQL query">SELECT borrower_id, name FROM borrowers ORDER BY name;</textarea>
      <div class="actions"><button id="run-sql" type="button">Run SQL query</button></div></div>
      </section>
    </div></div>
    <section class="card"><div class="results-heading"><h2>Results</h2><div id="result-actions" class="actions" hidden><button type="button" id="copy-results" class="secondary">Copy results with headers</button><button type="button" id="export-csv">Export to CSV</button></div></div><div id="query-status" class="muted" role="status">Choose a table or run a query.</div><div id="query-results" class="table-wrap"></div></section>`;

  document.getElementById("visual-mode-tab").onclick = () => chooseMode("visual");
  document.getElementById("sql-mode-tab").onclick = () => chooseMode("sql");
  document.getElementById("copy-results").onclick = copyResults;
  document.getElementById("export-csv").onclick = exportResultsCsv;
  document.getElementById("table-search").addEventListener("input", drawCatalog);
  document.getElementById("table-list").addEventListener("click", (event) => { const name = event.target.dataset.addTable; if (name) addTable(name); });
  document.getElementById("table-list").addEventListener("dragstart", (event) => { const card = event.target.closest(".table-card"); if (card) event.dataTransfer.setData("text/plain", card.dataset.table); });
  const canvas = document.getElementById("query-canvas");
  canvas.addEventListener("click", (event) => { const name = event.target.dataset.removeTable; if (name) removeTable(name); });
  canvas.addEventListener("dragover", (event) => { event.preventDefault(); canvas.classList.add("drag-over"); });
  canvas.addEventListener("dragleave", () => canvas.classList.remove("drag-over"));
  canvas.addEventListener("drop", (event) => { event.preventDefault(); canvas.classList.remove("drag-over"); addTable(event.dataTransfer.getData("text/plain")); });
  canvas.addEventListener("change", (event) => {
    if (!event.target.matches(".field-check")) return;
    const key = keyOf(event.target.dataset.table, event.target.dataset.column);
    if (event.target.checked) selectedColumns.add(key); else selectedColumns.delete(key);
    renderSelectAll();
  });
  document.getElementById("select-all-columns").addEventListener("change", (event) => {
    for (const field of allCanvasFields()) {
      const key = keyOf(field.table, field.column);
      if (event.target.checked) selectedColumns.add(key); else selectedColumns.delete(key);
    }
    renderCanvas();
  });
  document.getElementById("run-visual").onclick = () => runQuery({ mode: "visual", spec: visualSpec() }, true);
  document.getElementById("run-sql").onclick = () => runQuery({ mode: "sql", sql: document.getElementById("sql-input").value });
  document.getElementById("clear-visual").onclick = clearVisual;
  renderCanvas();
  chooseMode("visual");
}

async function start() {
  try {
    const session = await getJson(`/api/session?as_user=${encodeURIComponent(userId)}`);
    setHeader(session);
    const catalog = await getJson(`/api/database/catalog?as_user=${encodeURIComponent(session.userId)}`);
    schema = catalog.tables;
    joinTypes = catalog.joinTypes;
    renderUtility();
    drawCatalog();
  } catch (error) {
    main.innerHTML = `<section class="card error"><h1>Unable to open the database utility</h1><p>${esc(error.message)}</p><p><a href="/">Return to the borrower list</a></p></section>`;
  }
}

start();
