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
  results: document.getElementById("results"),
  resultsMeta: document.getElementById("resultsMeta"),
  details: document.getElementById("details"),
  resultTemplate: document.getElementById("resultTemplate"),
};

let syncPollHandle = null;

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

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

async function runSearch(event) {
  if (event) event.preventDefault();
  const params = new URLSearchParams({
    q: els.queryInput.value,
    active_only: String(els.activeOnlyInput.checked),
    has_media: String(els.hasMediaInput.checked),
  });
  if (els.authorInput.value.trim()) params.set("author", els.authorInput.value.trim());
  if (els.langInput.value.trim()) params.set("lang", els.langInput.value.trim());

  const result = await fetchJson(`/api/search?${params.toString()}`);
  els.resultsMeta.textContent = `${result.total} result(s)`;
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
    fragment.querySelector(".media-badge").textContent = item.has_media ? "media" : "text";
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
    <p><strong>Hashtags:</strong> ${tags}</p>
    <p><strong>Mentions:</strong> ${mentions}</p>
    <div><strong>URLs:</strong> ${urls}</div>
    <div><strong>Media:</strong> ${mediaHtml}</div>
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

els.searchForm.addEventListener("submit", runSearch);

document.addEventListener("DOMContentLoaded", async () => {
  await refreshStatus();
  await runSearch();
});
