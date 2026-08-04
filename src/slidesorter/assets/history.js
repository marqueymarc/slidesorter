const list = document.querySelector("#history-list");
const undoLast = document.querySelector("#history-undo-last");
const escapeHtml = value => String(value).replace(/[&<>'"]/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[character]);
let activePreview = null;
const iconPaths = {
  trash: '<path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5m4-5v5"/>',
  tray: '<path d="M12 15V3m0 0L7 8m5-5 5 5M4 14v6h16v-6"/>',
  archive: '<path d="M4 7h16v13H4zM3 4h18v3H3zm6 8h6"/>',
  star: '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9z"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
};
const iconMarkup = icon => `<svg class="action-glyph" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${iconPaths[icon] || iconPaths.arrow}</svg>`;

function toast(message, error = false) {
  const item = document.createElement("div");
  item.className = `toast ${error ? "error" : ""}`;
  item.innerHTML = `<span class="toast-message">${escapeHtml(message)}</span>`;
  document.querySelector("#toasts").append(item);
  setTimeout(() => item.remove(), 5000);
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "The request failed");
  return result;
}

function closePreview(restoreFocus = false) {
  if (!activePreview) return;
  activePreview.container.querySelector("video")?.pause();
  activePreview.container.replaceChildren();
  activePreview.container.hidden = true;
  activePreview.article.classList.remove("preview-open");
  activePreview.button.setAttribute("aria-expanded", "false");
  if (restoreFocus && activePreview.button.isConnected) activePreview.button.focus();
  activePreview = null;
}

function openPreview(button) {
  if (activePreview?.button === button) { closePreview(true); return; }
  closePreview();
  const article = button.closest(".history-item");
  const container = article.querySelector(".history-expanded");
  const kind = button.dataset.kind;
  const mediaUrl = button.dataset.media;
  const name = button.dataset.name;
  const media = kind === "video"
    ? `<video class="history-media" src="${escapeHtml(mediaUrl)}" controls playsinline preload="metadata" autoplay></video>`
    : `<img class="history-media" src="${escapeHtml(mediaUrl)}" alt="Expanded preview of ${escapeHtml(name)}">`;
  container.innerHTML = `<div class="history-expanded-head"><strong>${escapeHtml(name)}</strong><div><a class="history-open" href="${escapeHtml(mediaUrl)}" target="_blank" rel="noopener">Open full size ↗</a><button class="history-close" type="button" aria-label="Close preview">×</button></div></div><div class="history-media-frame">${media}</div>`;
  container.hidden = false;
  article.classList.add("preview-open");
  button.setAttribute("aria-expanded", "true");
  activePreview = { article, button, container };
  const mediaElement = container.querySelector(".history-media");
  mediaElement.addEventListener("error", () => toast(`${name} is no longer available`, true), { once: true });
  if (kind === "video") mediaElement.play().catch(() => {});
  container.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function render(result) {
  closePreview();
  undoLast.disabled = !result.can_undo;
  if (!result.entries.length) {
    list.innerHTML = `<div class="empty">No recorded moves yet. New destination actions will appear here.</div>`;
    return;
  }
  list.innerHTML = result.entries.map(entry => {
    const active = entry.status === "moved";
    const status = entry.status === "undone" ? `Undone ${escapeHtml(entry.undone_label || "")}` : active ? "Ready to undo" : escapeHtml(entry.status);
    const previewId = `history-preview-${escapeHtml(entry.entry_id)}`;
    const thumbnail = entry.thumbnail_url
      ? `<img class="history-thumb" src="${escapeHtml(entry.thumbnail_url)}" alt="" loading="lazy">`
      : `<span class="history-thumb history-thumb-empty"></span>`;
    const previewLabel = entry.kind === "video" ? `Play ${entry.name} here` : `Expand ${entry.name}`;
    const preview = `<button class="history-preview" type="button" data-media="${escapeHtml(entry.media_url)}" data-kind="${escapeHtml(entry.kind)}" data-name="${escapeHtml(entry.name)}" aria-label="${escapeHtml(previewLabel)}" aria-controls="${previewId}" aria-expanded="false">${thumbnail}<span class="history-preview-action" aria-hidden="true">${entry.kind === "video" ? "▶" : "↗"}</span></button>`;
    const batch = Number(entry.batch_size || 1);
    const meta = batch > 1 ? `${escapeHtml(entry.created_label)} · ${batch.toLocaleString()}-item batch` : escapeHtml(entry.created_label);
    return `<article class="history-item"><span class="history-pill tone-${escapeHtml(entry.action_tone)}">${iconMarkup(entry.action_icon)}${escapeHtml(entry.action_label)}</span>${preview}<div class="history-paths"><h2 class="history-name">${escapeHtml(entry.name)}</h2><div class="history-route" title="${escapeHtml(entry.source)}">${escapeHtml(entry.source)} → ${escapeHtml(entry.destination)}</div><div class="history-meta">${meta}</div></div><div>${active ? `<button class="button history-undo" type="button" data-token="${escapeHtml(entry.token)}">${batch > 1 ? "Undo batch" : "Undo"}</button>` : `<span class="history-status">${status}</span>`}</div><div class="history-expanded" id="${previewId}" hidden></div></article>`;
  }).join("");
}

async function loadHistory() {
  try { render(await request("/api/history?limit=500")); }
  catch (error) { list.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`; }
}

async function undo(token = null) {
  try {
    const result = await request("/api/undo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(token ? { token } : {}) });
    toast(`${result.name} restored`);
    await loadHistory();
  } catch (error) { toast(error.message, true); }
}

list.addEventListener("click", event => {
  const undoButton = event.target.closest(".history-undo");
  if (undoButton) { undo(undoButton.dataset.token); return; }
  const closeButton = event.target.closest(".history-close");
  if (closeButton) { closePreview(true); return; }
  const previewButton = event.target.closest(".history-preview");
  if (previewButton) openPreview(previewButton);
});
undoLast.addEventListener("click", () => undo());
document.querySelector("#history-refresh").addEventListener("click", loadHistory);
document.addEventListener("keydown", event => { if (event.key === "Escape") closePreview(true); });
loadHistory();
