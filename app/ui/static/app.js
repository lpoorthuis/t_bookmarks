const els = {
  loginButton: document.getElementById("loginButton"),
  logoutButton: document.getElementById("logoutButton"),
  syncButton: document.getElementById("syncButton"),
  connectionStatus: document.getElementById("connectionStatus"),
  userInfo: document.getElementById("userInfo"),
  bookmarkCount: document.getElementById("bookmarkCount"),
  lastSync: document.getElementById("lastSync"),
  syncStatus: document.getElementById("syncStatus"),
  syncMessage: document.getElementById("syncMessage"),
  searchForm: document.getElementById("searchForm"),
  queryInput: document.getElementById("queryInput"),
  activeOnlyInput: document.getElementById("activeOnlyInput"),
  hasMediaInput: document.getElementById("hasMediaInput"),
  authorInput: document.getElementById("authorInput"),
  langInput: document.getElementById("langInput"),
  sortBySelect: document.getElementById("sortBySelect"),
  sortOrderSelect: document.getElementById("sortOrderSelect"),
  addFilterButton: document.getElementById("addFilterButton"),
  filterRows: document.getElementById("filterRows"),
  filterRowTemplate: document.getElementById("filterRowTemplate"),
  results: document.getElementById("results"),
  resultsMeta: document.getElementById("resultsMeta"),
  details: document.getElementById("details"),
  resultTemplate: document.getElementById("resultTemplate"),
};

const OPERATOR_LABELS = {
  eq: "equals",
  ne: "not equals",
  contains: "contains",
  not_contains: "does not contain",
  starts_with: "starts with",
  ends_with: "ends with",
  gt: ">",
  gte: ">=",
  lt: "<",
  lte: "<=",
  in: "in list",
  not_in: "not in list",
  is_null: "is empty",
  is_not_null: "is not empty",
};

let syncPollHandle = null;
let propertyDefinitions = [];
let propertyMap = new Map();

const FALLBACK_PROPERTIES = [
  { key: "post.created_at", label: "Post created at", operators: ["eq", "ne", "gt", "gte", "lt", "lte"], sortable: true, filterable: true, type: "datetime" },
  { key: "bookmark.first_seen_at", label: "Bookmark first seen at", operators: ["eq", "ne", "gt", "gte", "lt", "lte"], sortable: true, filterable: true, type: "datetime" },
  { key: "bookmark.last_seen_at", label: "Bookmark last seen at", operators: ["eq", "ne", "gt", "gte", "lt", "lte"], sortable: true, filterable: true, type: "datetime" },
  { key: "post.metrics.like_count", label: "Like count", operators: ["eq", "ne", "gt", "gte", "lt", "lte"], sortable: true, filterable: true, type: "number" },
  { key: "author.username", label: "Author username", operators: ["eq", "ne", "contains", "starts_with", "ends_with"], sortable: true, filterable: true, type: "text" },
];

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json();
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

async function loadPropertyDefinitions() {
  try {
    const payload = await fetchJson("/api/search/properties");
    propertyDefinitions = payload.properties;
  } catch (error) {
    console.error("Failed to load property definitions, using fallback properties", error);
    propertyDefinitions = FALLBACK_PROPERTIES;
  }
  propertyMap = new Map(propertyDefinitions.map((item) => [item.key, item]));

  els.sortBySelect.innerHTML = "";
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = "Default relevance / last seen";
  els.sortBySelect.appendChild(defaultOption);

  for (const property of propertyDefinitions.filter((item) => item.sortable)) {
    const option = document.createElement("option");
    option.value = property.key;
    option.textContent = property.label;
    els.sortBySelect.appendChild(option);
  }
  els.sortBySelect.value = propertyMap.has("bookmark.last_seen_at") ? "bookmark.last_seen_at" : "post.created_at";
}

async function refreshStatus() {
  const [auth, appStatus] = await Promise.all([
    fetchJson("/auth/status"),
    fetchJson("/api/status"),
  ]);

  els.connectionStatus.textContent = auth.connected ? "Connected" : "Not connected";
  els.userInfo.textContent = auth.connected ? `${auth.user.name || ""} @${auth.user.username || ""}`.trim() : "-";
  els.bookmarkCount.textContent = String(appStatus.bookmark_count ?? 0);
  els.lastSync.textContent = formatDate(appStatus.last_sync_at);
  renderSyncStatus(appStatus.sync);
}

function renderSyncStatus(sync) {
  els.syncStatus.textContent = sync.running ? "Running" : sync.error ? "Failed" : "Idle";
  els.syncMessage.textContent = sync.error || sync.message || "";
  if (sync.running && !syncPollHandle) {
    syncPollHandle = setInterval(pollSyncStatus, 1500);
  } else if (!sync.running && syncPollHandle) {
    clearInterval(syncPollHandle);
    syncPollHandle = null;
  }
}

async function pollSyncStatus() {
  const sync = await fetchJson("/api/sync/status");
  renderSyncStatus(sync);
  if (!sync.running) {
    await refreshStatus();
    await runSearch();
  }
}

function createOption(value, label) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  return option;
}

function updateFilterOperatorOptions(row) {
  const fieldSelect = row.querySelector(".filter-field");
  const operatorSelect = row.querySelector(".filter-operator");
  const valueInput = row.querySelector(".filter-value");
  const definition = propertyMap.get(fieldSelect.value);
  operatorSelect.innerHTML = "";
  if (!definition) return;

  for (const operator of definition.operators) {
    operatorSelect.appendChild(createOption(operator, OPERATOR_LABELS[operator] || operator));
  }

  if (!definition.operators.includes(operatorSelect.value)) {
    operatorSelect.value = definition.operators[0];
  }
  updateFilterValueState(row);

  if (definition.type === "boolean") {
    valueInput.placeholder = "true / false";
  } else if (definition.type === "number") {
    valueInput.placeholder = "Number";
  } else if (definition.type === "datetime") {
    valueInput.placeholder = "2026-04-19T12:00:00+00:00";
  } else if (definition.type === "json") {
    valueInput.placeholder = "Text or JSON fragment";
  } else {
    valueInput.placeholder = "Value";
  }
}

function updateFilterValueState(row) {
  const operator = row.querySelector(".filter-operator").value;
  const valueInput = row.querySelector(".filter-value");
  const noValueNeeded = operator === "is_null" || operator === "is_not_null";
  valueInput.disabled = noValueNeeded;
  if (noValueNeeded) {
    valueInput.value = "";
  }
}

function addFilterRow(rule = {}) {
  const fragment = els.filterRowTemplate.content.cloneNode(true);
  const row = fragment.querySelector(".filter-row");
  const fieldSelect = row.querySelector(".filter-field");
  const operatorSelect = row.querySelector(".filter-operator");
  const valueInput = row.querySelector(".filter-value");
  const removeButton = row.querySelector(".remove-filter");

  for (const property of propertyDefinitions.filter((item) => item.filterable)) {
    fieldSelect.appendChild(createOption(property.key, property.label));
  }

  fieldSelect.value = rule.field || "post.full_text";
  updateFilterOperatorOptions(row);
  operatorSelect.value = rule.operator || operatorSelect.value;
  valueInput.value = rule.value ?? "";
  updateFilterValueState(row);

  fieldSelect.addEventListener("change", () => updateFilterOperatorOptions(row));
  operatorSelect.addEventListener("change", () => updateFilterValueState(row));
  removeButton.addEventListener("click", () => row.remove());

  els.filterRows.appendChild(fragment);
}

function collectFilters() {
  const rows = [...els.filterRows.querySelectorAll(".filter-row")];
  const filters = [];
  for (const row of rows) {
    const field = row.querySelector(".filter-field").value;
    const operator = row.querySelector(".filter-operator").value;
    const valueInput = row.querySelector(".filter-value");
    const value = valueInput.disabled ? null : valueInput.value;
    if (!field || !operator) continue;
    if (!valueInput.disabled && value === "") continue;
    filters.push({ field, operator, value });
  }
  return filters;
}

async function runSearch(event) {
  if (event) event.preventDefault();

  const filters = collectFilters();
  const params = new URLSearchParams({
    q: els.queryInput.value,
    active_only: String(els.activeOnlyInput.checked),
    has_media: String(els.hasMediaInput.checked),
    sort_order: els.sortOrderSelect.value,
  });

  if (els.authorInput.value.trim()) params.set("author", els.authorInput.value.trim());
  if (els.langInput.value.trim()) params.set("lang", els.langInput.value.trim());
  if (els.sortBySelect.value) params.set("sort_by", els.sortBySelect.value);
  if (filters.length) params.set("filters", JSON.stringify(filters));

  const result = await fetchJson(`/api/search?${params.toString()}`);
  const sortLabel = result.sort_by ? propertyMap.get(result.sort_by)?.label || result.sort_by : "default";
  els.resultsMeta.textContent = `${result.total} result(s) • sorted by ${sortLabel} (${result.sort_order})`;
  els.results.innerHTML = "";

  if (!result.results.length) {
    els.results.innerHTML = '<p class="muted">No results.</p>';
    return;
  }

  for (const item of result.results) {
    const fragment = els.resultTemplate.content.cloneNode(true);
    fragment.querySelector(".author-name").textContent = item.author.name || "Unknown";
    fragment.querySelector(".author-username").textContent = item.author.username ? `@${item.author.username}` : "";
    fragment.querySelector(".result-date").textContent = formatDate(item.created_at);
    fragment.querySelector(".result-snippet").textContent = item.snippet || item.text;
    fragment.querySelector(".media-badge").textContent = item.has_media ? `${item.media_count} media` : "text only";
    fragment.querySelector(".metrics-badge").textContent = `❤ ${item.metrics.like_count} · ↻ ${item.metrics.retweet_count} · 💬 ${item.metrics.reply_count}`;
    fragment.querySelector(".open-link").href = item.url;
    fragment.querySelector(".details-button").addEventListener("click", () => loadDetails(item.post_id));
    els.results.appendChild(fragment);
  }
}

async function loadDetails(postId) {
  const post = await fetchJson(`/api/post/${postId}`);
  const mediaHtml = post.media.length
    ? `<ul>${post.media.map((m) => `<li>${escapeHtml(m.type || "media")}${m.url ? ` - <a href="${m.url}" target="_blank" rel="noopener noreferrer">link</a>` : ""}</li>`).join("")}</ul>`
    : '<p class="muted">No media.</p>';

  const tags = post.entities.hashtags.length ? post.entities.hashtags.map((t) => `#${escapeHtml(t)}`).join(" ") : "-";
  const mentions = post.entities.mentions.length ? post.entities.mentions.map((m) => `@${escapeHtml(m)}`).join(" ") : "-";
  const urls = post.entities.urls.length
    ? `<ul>${post.entities.urls.map((u) => `<li><a href="${u}" target="_blank" rel="noopener noreferrer">${escapeHtml(u)}</a></li>`).join("")}</ul>`
    : "-";

  els.details.innerHTML = `
    <p><strong>${escapeHtml(post.author.name || "Unknown")}</strong> ${post.author.username ? `@${escapeHtml(post.author.username)}` : ""}</p>
    <p class="muted">${formatDate(post.created_at)}</p>
    <p>${escapeHtml(post.text)}</p>
    <p><strong>Conversation ID:</strong> ${escapeHtml(post.conversation_id || "-")}</p>
    <p><strong>Public metrics:</strong> ❤ ${escapeHtml(post.public_metrics.like_count ?? 0)} · ↻ ${escapeHtml(post.public_metrics.retweet_count ?? 0)} · 💬 ${escapeHtml(post.public_metrics.reply_count ?? 0)} · ❝ ${escapeHtml(post.public_metrics.quote_count ?? 0)}</p>
    <p><strong>Hashtags:</strong> ${tags}</p>
    <p><strong>Mentions:</strong> ${mentions}</p>
    <div><strong>URLs:</strong> ${urls}</div>
    <div><strong>Media:</strong> ${mediaHtml}</div>
    <p><strong>First seen:</strong> ${escapeHtml(formatDate(post.first_seen_at))}</p>
    <p><strong>Last seen:</strong> ${escapeHtml(formatDate(post.last_seen_at))}</p>
    <p><strong>Inactive at:</strong> ${escapeHtml(formatDate(post.inactive_at))}</p>
    <p><strong>Last sync run:</strong> ${escapeHtml(post.last_sync_run_id ?? "-")}</p>
    <p><a href="${post.x_url}" target="_blank" rel="noopener noreferrer">Open on X</a></p>
    <details>
      <summary>Raw JSON</summary>
      <pre>${escapeHtml(JSON.stringify(post.raw_json, null, 2))}</pre>
    </details>
  `;
}

els.loginButton.addEventListener("click", () => {
  window.location.href = "/auth/login";
});

els.logoutButton.addEventListener("click", async () => {
  await fetchJson("/auth/logout", { method: "POST" });
  await refreshStatus();
  await runSearch();
});

els.syncButton.addEventListener("click", async () => {
  await fetchJson("/api/sync/start?full=true", { method: "POST" });
  await pollSyncStatus();
});

els.addFilterButton.addEventListener("click", () => addFilterRow());
els.searchForm.addEventListener("submit", runSearch);

document.addEventListener("DOMContentLoaded", async () => {
  await loadPropertyDefinitions();
  await refreshStatus();
  await runSearch();
});
