const API = "/api";
const main = document.getElementById("app-content");
const params = new URLSearchParams(window.location.search);
const userId = params.get("as_user") || "superuser";
const borrowerId = window.location.pathname === "/borrower" ? params.get("id") : null;

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
})[character]);
const money = (value, currency) => `${currency} ${Number(value || 0).toLocaleString("en-CA", { maximumFractionDigits: 0 })}`;
const percent = (value) => value === null || value === undefined ? "—" : `${Number(value).toFixed(1)}%`;
const utilization = (value) => {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  const amount = Number(value);
  return `<span class="utilization-value">${percent(amount)}<span class="utilization-track" aria-hidden="true"><span class="utilization-fill" style="width:${Math.min(100, Math.max(0, amount))}%"></span></span></span>`;
};

function animateCount(element, target) {
  const goal = Number(target);
  if (!Number.isFinite(goal)) return;
  const formatter = new Intl.NumberFormat("en-CA", { maximumFractionDigits: 0 });
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
    element.textContent = formatter.format(goal);
    return;
  }
  const start = performance.now();
  const duration = 560;
  const tick = (now) => {
    const progress = Math.min(1, (now - start) / duration);
    const eased = 1 - (1 - progress) ** 3;
    element.textContent = formatter.format(Math.round(goal * eased));
    if (progress < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

async function getJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "The app could not load this page.");
  return payload;
}

function withUser(path, id = userId) {
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}as_user=${encodeURIComponent(id)}`;
}

function setHeader(session) {
  const selector = document.getElementById("as-user");
  selector.innerHTML = session.users.map((user) =>
    `<option value="${esc(user.userId)}"${user.userId === session.userId ? " selected" : ""}>${esc(user.displayName)}</option>`
  ).join("");
  document.getElementById("brand-link").href = withUser("/");
  const databaseLink = document.getElementById("database-link");
  databaseLink.hidden = false;
  const databaseUrl = new URL("/database", window.location.origin);
  databaseUrl.searchParams.set("as_user", session.userId);
  databaseUrl.searchParams.set("return_to", `${window.location.pathname}${window.location.search}`);
  databaseLink.href = `${databaseUrl.pathname}${databaseUrl.search}`;
  document.getElementById("role-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const nextUser = selector.value;
    const path = borrowerId
      ? `/borrower?id=${encodeURIComponent(borrowerId)}&as_user=${encodeURIComponent(nextUser)}`
      : withUser("/", nextUser);
    window.location.assign(path);
  }, { once: true });
}

function renderPortfolio(data) {
  const { session, borrowers } = data;
  setHeader(session);
  main.dataset.currency = "CAD";
  const sectors = [...new Set(borrowers.map((row) => row.sector))].sort((a, b) => a.localeCompare(b));
  const facilityCount = borrowers.reduce((total, row) => total + row.visibleFacilityCount, 0);
  const accessTags = session.access.map((line, index) => `<span class="access-tag" style="--tag-index:${index}">${esc(line)}</span>`).join("");
  let recentIds = [];
  try {
    const storedRecentIds = JSON.parse(localStorage.getItem("northstar-recent-borrowers") || "[]");
    if (Array.isArray(storedRecentIds)) recentIds = storedRecentIds;
  } catch { recentIds = []; }
  const recentBorrowers = recentIds.map((id) => borrowers.find((row) => String(row.borrowerId) === String(id))).filter(Boolean).slice(0, 5);
  const summaryAmount = (row) => row.visibleFacilityCount > 1
    ? `<span class="currency-value show-cad">${money(row.summary.totalCad, "CAD")}</span><span class="currency-value show-usd">${money(row.summary.totalUsd, "USD")}</span>`
    : `<span class="detail">Exposure summary</span>`;
  const card = (row) => {
    const link = `/borrower?id=${encodeURIComponent(row.borrowerId)}&as_user=${encodeURIComponent(session.userId)}`;
    const searchable = [row.name, row.borrowerId, row.sector, ...row.teams.map((team) => `${team.lineOfBusiness} ${team.role} ${team.name}`)].join(" ").toLocaleLowerCase();
    const utilizationValue = Number(row.utilizationPct || 0);
    const ringValue = Math.min(100, Math.max(0, utilizationValue));
    return `<article class="borrower-card" data-search="${esc(searchable)}" data-sector="${esc(row.sector)}">
      <div class="borrower-card-top"><span class="sector-tag">${esc(row.sector)}</span><span class="relationship-id">ID ${esc(row.borrowerId)}</span></div>
      <h3><a href="${link}">${esc(row.name)}</a></h3>
      <div class="borrower-card-metrics"><div><span class="metric-label">Reported exposure</span><strong>${summaryAmount(row)}</strong><span class="card-facilities">${row.visibleFacilityCount > 1 ? `${row.visibleFacilityCount} facility details in view` : "Limited facility detail view"}</span></div>
        <div class="utilization-dial" style="--dial-value:${ringValue}%"><span>${percent(row.utilizationPct)}</span><small>utilized</small></div></div>
      <div class="borrower-card-bottom"><span>${row.teams.length} account team contact${row.teams.length === 1 ? "" : "s"}</span><a href="${link}" aria-label="Open ${esc(row.name)} relationship">Explore <span aria-hidden="true">↗</span></a></div>
    </article>`;
  };
  const rows = borrowers.map((row) => {
    const link = `/borrower?id=${encodeURIComponent(row.borrowerId)}&as_user=${encodeURIComponent(session.userId)}`;
    const searchable = [row.name, row.borrowerId, row.sector, ...row.teams.map((team) => `${team.lineOfBusiness} ${team.role} ${team.name}`)].join(" ").toLocaleLowerCase();
    return `<tr data-search="${esc(searchable)}" data-sector="${esc(row.sector)}"><td><a class="borrower-table-name" href="${link}">${esc(row.name)}</a><div class="detail">Borrower ID: ${esc(row.borrowerId)}</div></td><td><span class="sector-tag">${esc(row.sector)}</span></td><td>${summaryAmount(row)}<div class="detail">Utilization ${percent(row.utilizationPct)}</div></td><td>${row.teams.length} contacts</td><td><a href="${link}" aria-label="Open ${esc(row.name)}">Open ↗</a></td></tr>`;
  }).join("");
  main.innerHTML = `<div class="portfolio-dashboard" data-currency="CAD">
    <section class="dashboard-hero"><div class="hero-copy"><div class="eyebrow">NORTHSTAR · PORTFOLIO OVERVIEW</div><h1>Your book, in focus.</h1><p>Good morning, ${esc(session.displayName)}. Explore borrower relationships and see the shape of your portfolio.</p><div class="hero-access"><span class="hero-access-label">Viewing across</span>${accessTags || `<span class="access-tag">No lines assigned</span>`}</div></div>
      <div class="hero-art" aria-hidden="true"><div class="hero-orbit orbit-one"></div><div class="hero-orbit orbit-two"></div><div class="hero-orbit orbit-three"></div><div class="hero-spark">✳</div><div class="hero-note"><span>Relationships</span><strong>${borrowers.length}</strong><small>in your portfolio</small></div></div></section>
    <section class="overview-metrics" aria-label="Portfolio at a glance">
      <article class="overview-tile"><span class="tile-icon icon-blue">◫</span><div><span class="metric-label">Borrower relationships</span><strong data-count-to="${borrowers.length}">0</strong><small>Across ${sectors.length} sectors</small></div></article>
      <article class="overview-tile"><span class="tile-icon icon-gold">⌁</span><div><span class="metric-label">Facility records in view</span><strong data-count-to="${facilityCount}">0</strong><small>Based on current role</small></div></article>
      <article class="overview-tile"><span class="tile-icon icon-lilac">◎</span><div><span class="metric-label">Lines of business</span><strong data-count-to="${session.access.length || 0}">0</strong><small>${session.isSuperuser ? "Superuser view" : "Access assigned to you"}</small></div></article>
    </section>
    ${recentBorrowers.length ? `<section class="recent-section"><div class="recent-heading"><div><span class="eyebrow">PICK UP WHERE YOU LEFT OFF</span><h2>Recently viewed</h2></div><span class="recent-caption">On this device</span></div><div class="recent-list">${recentBorrowers.map((row) => `<a class="recent-link" href="/borrower?id=${encodeURIComponent(row.borrowerId)}&as_user=${encodeURIComponent(session.userId)}"><span class="recent-icon">${esc(row.name.split(/\s+/).slice(0, 2).map((part) => part[0]).join(""))}</span><span><strong>${esc(row.name)}</strong><small>${esc(row.sector)} · ID ${esc(row.borrowerId)}</small></span><span class="recent-arrow" aria-hidden="true">↗</span></a>`).join("")}</div></section>` : ""}
    <section class="portfolio-section"><div class="section-heading"><div><div class="eyebrow">RELATIONSHIP DIRECTORY</div><h2>Borrowers</h2><p>Find a name, sector, or account contact to open a relationship.</p></div><div class="currency-control" role="group" aria-label="Exposure currency"><span>Show in</span><button type="button" data-currency="CAD" aria-pressed="true">CAD</button><button type="button" data-currency="USD" aria-pressed="false">USD</button></div></div>
      <div class="directory-toolbar"><div class="directory-search-wrap"><span aria-hidden="true">⌕</span><input id="borrower-search" class="search-box" type="search" placeholder="Search borrowers, contacts, or IDs" aria-label="Search borrower directory"></div>
        <label class="sector-filter-label" for="sector-filter">Sector <select id="sector-filter"><option value="">All sectors</option>${sectors.map((sector) => `<option value="${esc(sector)}">${esc(sector)}</option>`).join("")}</select></label>
        <div class="view-switch" role="group" aria-label="Directory layout"><button type="button" data-view="cards" aria-pressed="true" aria-label="Card view">▦</button><button type="button" data-view="table" aria-pressed="false" aria-label="Table view">☷</button></div>
        <span id="borrower-count" class="directory-count">${borrowers.length} relationships</span></div>
      <div id="borrower-results" class="borrower-results" data-layout="cards"><div id="borrower-cards" class="borrower-card-grid">${borrowers.map(card).join("")}</div>
        <div class="borrower-table-wrap"><table class="borrower-table"><thead><tr><th>Borrower</th><th>Sector</th><th>Reported exposure</th><th>Account team</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
        <div id="borrower-empty" class="empty-state" hidden><span aria-hidden="true">⌕</span><strong>No relationships found</strong><p>Try another name or clear the sector filter.</p></div></div>
      <p class="portfolio-note"><span class="note-dot"></span>Borrower totals and account teams can span lines of business. Facility details shown on the borrower page follow your selected role.</p>
    </section>
  </div>`;
  const search = document.getElementById("borrower-search");
  const sectorFilter = document.getElementById("sector-filter");
  const resultHost = document.getElementById("borrower-results");
  main.querySelectorAll("[data-count-to]").forEach((element) => animateCount(element, element.dataset.countTo));
  const updateDirectory = () => {
    const query = search.value.trim().toLocaleLowerCase();
    const sector = sectorFilter.value;
    const entries = resultHost.querySelectorAll("[data-search]");
    let visible = 0;
    for (const entry of entries) {
      const match = (!query || entry.dataset.search.includes(query)) && (!sector || entry.dataset.sector === sector);
      entry.hidden = !match;
      if (match && entry.matches("article")) visible += 1;
    }
    document.getElementById("borrower-count").textContent = `${visible} of ${borrowers.length} relationships`;
    document.getElementById("borrower-empty").hidden = visible > 0;
  };
  search.addEventListener("input", updateDirectory);
  sectorFilter.addEventListener("change", updateDirectory);
  main.querySelectorAll(".view-switch button").forEach((button) => button.addEventListener("click", () => {
    resultHost.dataset.layout = button.dataset.view;
    main.querySelectorAll(".view-switch button").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
  }));
  main.querySelectorAll(".currency-control button").forEach((button) => button.addEventListener("click", () => {
    main.dataset.currency = button.dataset.currency;
    main.querySelectorAll(".currency-control button").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
  }));
}

function renderBreakdown(summary) {
  const rows = [];
  for (const [groupName, values] of Object.entries(summary.groups || {})) {
    rows.push(`<tr class="breakdown-group"><td>${esc(groupName)}</td><td class="show-cad">${money(values.cad, "CAD")}</td><td class="show-usd">${money(values.usd, "USD")}</td></tr>`);
    for (const [facilityType, amounts] of Object.entries(values.facilityTypes || {})) {
      rows.push(`<tr><td class="detail breakdown-child">${esc(facilityType)}</td><td class="detail show-cad">${money(amounts.cad, "CAD")}</td><td class="detail show-usd">${money(amounts.usd, "USD")}</td></tr>`);
    }
  }
  return rows.join("") || `<tr><td colspan="3">No exposure recorded.</td></tr>`;
}

function renderFacilityRows(facilities) {
  return facilities.map((facility) => {
    const id = String(facility.facilityId);
    return `<tr class="facility-data-row" data-description-open="false">
      <td><a class="facility-disclosure-link" href="#facility-description-${id}" aria-controls="facility-description-${id}" aria-expanded="false" data-facility-id="${id}">${id}</a></td>
      <td>${esc(facility.lineOfBusiness)}</td><td>${esc(facility.exposureClass)} · ${esc(facility.exposureSubclass)}</td>
      <td>${esc(facility.facilityType)}</td><td><span class="status-badge${facility.status === "Active" ? "" : " inactive"}">${esc(facility.status)}</span></td>
      <td>${esc(facility.commitmentStartDate || "—")}</td><td>${esc(facility.maturityDate)}</td>
      <td>${esc(facility.currency)} · ${esc(facility.currencyDescription)}</td>
      <td>${Number(facility.committedAmount).toLocaleString("en-CA", { maximumFractionDigits: 0 })}</td>
      <td>${Number(facility.uncommittedAmount).toLocaleString("en-CA", { maximumFractionDigits: 0 })}</td>
      <td>${Number(facility.drawnAmount).toLocaleString("en-CA", { maximumFractionDigits: 0 })}</td>
      <td>${utilization(facility.utilizationPct)}</td></tr>
      <tr id="facility-description-${id}" class="facility-description-row" hidden><td colspan="12"><div class="facility-description"><strong>Facility description:</strong> ${esc(facility.description)}</div></td></tr>`;
  }).join("") || `<tr><td colspan="12" class="muted">No facility details are available to your user.</td></tr>`;
}

function setupFacilityTable() {
  const table = document.querySelector(".facility-table");
  if (!table) return;
  const body = table.tBodies[0];
  const pairs = Array.from(body.querySelectorAll("tr.facility-data-row"), (row) => ({ row, detail: row.nextElementSibling }));
  const filters = Array.from(table.querySelectorAll(".column-filter"));
  const buttons = Array.from(table.querySelectorAll(".sort-button"));
  const summary = document.getElementById("facility-filter-summary");
  let sortIndex = -1;
  let ascending = true;
  const valueFor = (pair, index) => index === 0
    ? pair.row.querySelector(".facility-disclosure-link").dataset.facilityId
    : (pair.row.cells[index]?.textContent.trim() || "");
  const apply = () => {
    const criteria = filters.map((input) => ({ index: Number(input.dataset.filterIndex), value: input.value.trim().toLocaleLowerCase() })).filter((item) => item.value);
    if (summary) summary.textContent = criteria.length ? `${criteria.length} filter${criteria.length === 1 ? "" : "s"} applied` : `${pairs.length} facilities`;
    for (const pair of pairs) {
      const visible = criteria.every((criterion) => valueFor(pair, criterion.index).toLocaleLowerCase().includes(criterion.value));
      pair.row.hidden = !visible;
      pair.detail.hidden = !visible || pair.row.dataset.descriptionOpen !== "true";
    }
    if (sortIndex >= 0) {
      const type = buttons.find((button) => Number(button.dataset.sortIndex) === sortIndex)?.dataset.sortType;
      pairs.sort((left, right) => {
        const a = valueFor(left, sortIndex);
        const b = valueFor(right, sortIndex);
        const difference = type === "number" ? Number(a.replace(/,/g, "")) - Number(b.replace(/,/g, ""))
          : type === "percent" ? (parseFloat(a) || 0) - (parseFloat(b) || 0)
            : a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
        return ascending ? difference : -difference;
      });
    }
    for (const pair of pairs) body.append(pair.row, pair.detail);
  };
  table.addEventListener("click", (event) => {
    const link = event.target.closest(".facility-disclosure-link");
    if (link) {
      event.preventDefault();
      const detail = document.getElementById(link.getAttribute("aria-controls"));
      const open = link.getAttribute("aria-expanded") !== "true";
      detail.hidden = !open;
      link.closest("tr").dataset.descriptionOpen = String(open);
      link.setAttribute("aria-expanded", String(open));
      link.setAttribute("aria-label", `Facility ID ${link.dataset.facilityId}; ${open ? "hide" : "show"} description`);
      return;
    }
    const button = event.target.closest(".sort-button");
    if (!button) return;
    const next = Number(button.dataset.sortIndex);
    ascending = sortIndex === next ? !ascending : true;
    sortIndex = next;
    for (const item of buttons) {
      const active = Number(item.dataset.sortIndex) === sortIndex;
      item.closest("th").setAttribute("aria-sort", active ? (ascending ? "ascending" : "descending") : "none");
      item.querySelector(".sort-indicator").textContent = active ? (ascending ? "↑" : "↓") : "↕";
    }
    apply();
  });
  filters.forEach((input) => input.addEventListener("input", apply));
  document.getElementById("clear-facility-filters")?.addEventListener("click", () => {
    filters.forEach((input) => { input.value = ""; });
    apply();
    filters[0]?.focus();
  });
  apply();
}

function renderBorrowerDetail(data) {
  const { session, borrower } = data;
  setHeader(session);
  try {
    const storedRecent = JSON.parse(localStorage.getItem("northstar-recent-borrowers") || "[]");
    const recent = Array.isArray(storedRecent) ? storedRecent : [];
    const recentIds = [String(borrower.borrowerId), ...recent.map(String).filter((id) => id !== String(borrower.borrowerId))].slice(0, 5);
    localStorage.setItem("northstar-recent-borrowers", JSON.stringify(recentIds));
  } catch { /* Recent navigation is optional when browser storage is unavailable. */ }
  main.dataset.currency = "CAD";
  const utilizationValue = Number(borrower.utilizationPct || 0);
  const teamCards = borrower.teams.map((team, index) => `<article class="team-card" style="--team-index:${index}"><div class="team-monogram">${esc(team.name.split(/\s+/).map((part) => part[0]).slice(0, 2).join(""))}</div><div><span class="team-line">${esc(team.lineOfBusiness)} · ${esc(team.role)}</span><strong>${esc(team.name)}</strong></div><span class="team-arrow" aria-hidden="true">↗</span></article>`).join("") || `<p class="muted">No account team contacts recorded.</p>`;
  main.innerHTML = `<div class="borrower-detail">
    <p class="detail-breadcrumb"><a href="${withUser("/")}"><span aria-hidden="true">←</span> Portfolio</a><span>/</span><span>Borrower</span></p>
    <section class="borrower-sticky-row"><div><div class="eyebrow">BORROWER PROFILE</div><h1>${esc(borrower.name)}</h1></div><div class="sticky-profile-meta"><span class="sector-tag">${esc(borrower.sector)}</span><span>Borrower ID <strong>${esc(borrower.borrowerId)}</strong></span></div></section>
    <section class="detail-overview"><article class="exposure-hero-card"><div class="exposure-hero-top"><div><div class="eyebrow">TOTAL REPORTED EXPOSURE</div><h2>Borrower-wide view</h2></div><span class="hero-star" aria-hidden="true">✳</span></div><div class="exposure-hero-value"><span class="currency-value show-cad">${money(borrower.summary.totalCad, "CAD")}</span><span class="currency-value show-usd">${money(borrower.summary.totalUsd, "USD")}</span></div><div class="exposure-hero-bottom"><span>Converted portfolio total</span><div class="currency-control light" role="group" aria-label="Exposure currency"><button type="button" data-currency="CAD" aria-pressed="true">CAD</button><button type="button" data-currency="USD" aria-pressed="false">USD</button></div></div><div class="hero-card-pattern" aria-hidden="true"></div></article>
      <article class="utilization-card"><div><div class="eyebrow">OVERALL UTILIZATION</div><h2>Drawn against exposure</h2><p>CAD-equivalent basis</p></div><div class="utilization-dial large" style="--dial-value:${Math.min(100, Math.max(0, utilizationValue))}%"><span>${percent(borrower.utilizationPct)}</span><small>utilized</small></div><div class="utilization-card-caption">Drawn amounts stay separate from exposure.</div></article></section>
    <section class="detail-context"><span class="context-icon" aria-hidden="true">i</span><p>Exposure includes committed and uncommitted amounts for Active facilities. Drawn amounts are shown separately as utilization. An Active facility remains eligible after maturity.</p><span class="context-badge">${borrower.facilities.length} facility details available</span></section>
    <section class="content-section"><div class="section-heading"><div><div class="eyebrow">PORTFOLIO COMPOSITION</div><h2>Exposure breakdown</h2><p>Browse the borrower total by category and facility type.</p></div></div><div class="card breakdown-card"><div class="breakdown-legend"><span><i class="legend-dot blue"></i>Credit</span><span><i class="legend-dot gold"></i>Non-credit / other</span><span class="breakdown-currency">Amounts in <strong><span class="show-cad">CAD</span><span class="show-usd">USD</span></strong></span></div><div class="table-wrap"><table class="breakdown-table"><thead><tr><th>Facility category</th><th class="show-cad">Total (CAD)</th><th class="show-usd">Total (USD)</th></tr></thead><tbody>${renderBreakdown(borrower.summary)}</tbody></table></div></div></section>
    <section class="content-section"><div class="section-heading"><div><div class="eyebrow">PEOPLE BEHIND THE RELATIONSHIP</div><h2>Account team</h2><p>Contacts across the borrower's business relationships.</p></div><span class="section-count">${borrower.teams.length} contacts</span></div><div class="team-card-grid">${teamCards}</div></section>
    <section class="content-section facilities-section"><div class="section-heading"><div><div class="eyebrow">FACILITY DETAIL</div><h2>Facilities available to you</h2><p>${session.isSuperuser ? "All facility details are available in superuser view." : "Other lines of business are not listed in this role."}</p></div></div>
      <div class="facility-tools"><span id="facility-filter-summary" class="detail">${borrower.facilities.length} facilities</span><button id="clear-facility-filters" class="secondary" type="button">Clear filters</button></div>
      <div class="table-wrap"><table class="facility-table"><thead>
        <tr>${[
          ["Facility ID", "number"], ["Line of business", "text"], ["Class", "text"], ["Facility type", "text"], ["Status", "text"],
          ["Commitment start", "date"], ["Maturity", "date"], ["Currency", "text"], ["Committed", "number"], ["Uncommitted", "number"], ["Drawn / utilized", "number"], ["Utilization", "percent"]
        ].map(([label, type], index) => `<th aria-sort="none"><button class="sort-button" type="button" data-sort-index="${index}" data-sort-type="${type}">${label} <span class="sort-indicator">↕</span></button></th>`).join("")}</tr>
        <tr class="filter-row">${["facility ID", "line of business", "class", "facility type", "status", "commitment start date", "maturity date", "currency", "committed amount", "uncommitted amount", "drawn amount", "utilization"].map((label, index) => `<th><input class="column-filter" type="search" data-filter-index="${index}" aria-label="Filter by ${label}" placeholder="Filter"></th>`).join("")}</tr>
      </thead><tbody>${renderFacilityRows(borrower.facilities)}</tbody></table></div></section>
  </div>`;
  main.querySelectorAll(".currency-control button").forEach((button) => button.addEventListener("click", () => {
    main.dataset.currency = button.dataset.currency;
    main.querySelectorAll(".currency-control button").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
  }));
  setupFacilityTable();
}

async function start() {
  try {
    const route = borrowerId
      ? `/api/borrowers/${encodeURIComponent(borrowerId)}?as_user=${encodeURIComponent(userId)}`
      : `/api/borrowers?as_user=${encodeURIComponent(userId)}`;
    const data = await getJson(route);
    if (borrowerId) renderBorrowerDetail(data);
    else renderPortfolio(data);
  } catch (error) {
    main.innerHTML = `<section class="card error"><h1>Unable to load the app</h1><p>${esc(error.message)}</p><p><a href="/">Return to the borrower list</a></p></section>`;
  }
}

start();
