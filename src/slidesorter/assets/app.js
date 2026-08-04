const savedPageSize = Number(localStorage.getItem("media-gallery-page-size"));
const state = {
  catalog: null, query: "", sort: "oldest", kind: "both", active: null,
  page: 1, pageSize: savedPageSize >= 25 && savedPageSize <= 500 && savedPageSize % 25 === 0 ? savedPageSize : 100,
  requestNumber: 0, selectionAll: false, allCriteria: null,
  selectedIds: new Set(), excludedIds: new Set(), lastSelectedId: null,
};
const gallery = document.querySelector("#gallery");
const search = document.querySelector("#search");
const sort = document.querySelector("#sort");
const summary = document.querySelector("#summary");
const title = document.querySelector("#title");
const undoLast = document.querySelector("#undo-last");
const sheet = document.querySelector("#settings-sheet");
const scrim = document.querySelector("#settings-scrim");
const pageSize = document.querySelector("#page-size");
const previousPage = document.querySelector("#page-previous");
const nextPage = document.querySelector("#page-next");
const selectPage = document.querySelector("#select-page");
const selectAll = document.querySelector("#select-all");
const bulkBar = document.querySelector("#bulk-bar");
const pageNumber = document.querySelector("#page-number");
const pageTotal = document.querySelector("#page-total");
const destinationList = document.querySelector("#destination-list");
const bulkActions = document.querySelector("#bulk-actions");
pageSize.value = String(state.pageSize);

const escapeHtml = value => String(value).replace(/[&<>'"]/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[character]);

const iconPaths = {
  trash: '<path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5m4-5v5"/>',
  tray: '<path d="M12 15V3m0 0L7 8m5-5 5 5M4 14v6h16v-6"/>',
  archive: '<path d="M4 7h16v13H4zM3 4h18v3H3zm6 8h6"/>',
  star: '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9z"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
};

function iconMarkup(icon) {
  const path = iconPaths[icon] || iconPaths.arrow;
  return `<svg class="action-glyph" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
}

function actionPresentation(rawLabel) {
  const value = String(rawLabel || "").trim().replace(/\s+/g, " ");
  const match = value.match(/^(.+?)\s*\(([^()]*)\)\s*$/);
  const hintWords = /glyph|icon|color|colour|trash|trashcan|bin|delete|discard|remove|tray|stage|upload|import|inbox|archive|box|store|star|favorite|favourite|check|keep|approve|clock|later|review|hold|pending|red|danger|amber|orange|yellow|blue|green|mint|gray|grey|neutral|plain/i;
  const hint = match && hintWords.test(match[2]) ? match[2].toLowerCase() : "";
  const displayLabel = hint ? match[1].trim() : value;
  const semantics = `${displayLabel} ${hint}`.toLowerCase();
  const rules = [
    ["trash", /trash|trashcan|bin|delete|discard|remove/],
    ["tray", /tray|stage|upload|import|inbox/],
    ["archive", /archive|box|store|file away/],
    ["star", /star|favorite|favourite|best/],
    ["check", /check|keep|approve|accepted/],
    ["clock", /clock|later|review|hold|pending/],
  ];
  const tones = [
    ["danger", /red|danger|destructive|trash|delete|discard|remove/],
    ["amber", /amber|orange|yellow|star|favorite|archive/],
    ["blue", /blue|review|later|hold|clock/],
    ["mint", /green|mint|stage|upload|import|keep|approve|check/],
    ["neutral", /gray|grey|neutral|plain/],
  ];
  return {
    display_label: displayLabel || "Destination",
    icon: rules.find(([, pattern]) => pattern.test(semantics))?.[0] || "arrow",
    tone: tones.find(([, pattern]) => pattern.test(semantics))?.[0] || "neutral",
  };
}

function actionButtonMarkup(action, extraClass = "") {
  return `<button class="action move-action tone-${escapeHtml(action.tone)} ${extraClass}" type="button" data-action-id="${escapeHtml(action.id)}" title="Move to ${escapeHtml(action.display_label)}">${iconMarkup(action.icon)}<span>${escapeHtml(action.display_label)}</span></button>`;
}

function overflowMarkup(actions, extraClass = "") {
  if (!actions.length) return "";
  return `<div class="action-menu-wrap ${extraClass}"><button class="action more-actions" type="button" aria-haspopup="menu" aria-expanded="false">More <span aria-hidden="true">⌄</span></button><div class="action-menu" role="menu" hidden>${actions.map(action => `<button class="action-menu-item move-action tone-${escapeHtml(action.tone)}" type="button" role="menuitem" data-action-id="${escapeHtml(action.id)}">${iconMarkup(action.icon)}<span>${escapeHtml(action.display_label)}</span></button>`).join("")}</div></div>`;
}

function toast(message, options = {}) {
  const item = document.createElement("div");
  item.className = `toast ${options.error ? "error" : ""}`;
  if (options.thumbnail) {
    const image = document.createElement("img");
    image.className = "toast-thumb";
    image.src = options.thumbnail;
    image.alt = "";
    item.append(image);
  }
  const text = document.createElement("span");
  text.className = "toast-message";
  text.textContent = message;
  item.append(text);
  if (options.actionLabel && options.onAction) {
    const action = document.createElement("button");
    action.className = "toast-action";
    action.type = "button";
    action.textContent = options.actionLabel;
    action.addEventListener("click", async () => {
      action.disabled = true;
      await options.onAction();
      item.remove();
    });
    item.append(action);
  }
  document.querySelector("#toasts").append(item);
  setTimeout(() => item.remove(), options.duration || 9000);
}

function matchesAllCriteria(item) {
  if (!state.selectionAll || !state.allCriteria) return false;
  const query = state.allCriteria.query.toLocaleLowerCase();
  return (state.allCriteria.kind === "both" || item.kind === state.allCriteria.kind)
    && (!query || `${item.name} ${item.folder}`.toLocaleLowerCase().includes(query));
}

function isSelected(item) {
  if (state.selectedIds.has(item.id)) return true;
  return matchesAllCriteria(item) && !state.excludedIds.has(item.id);
}

function selectedCount() {
  if (!state.selectionAll) return state.selectedIds.size;
  return Math.max(0, state.allCriteria.total - state.excludedIds.size + state.selectedIds.size);
}

function clearSelection() {
  state.selectionAll = false;
  state.allCriteria = null;
  state.selectedIds.clear();
  state.excludedIds.clear();
  state.lastSelectedId = null;
  updateSelectionUI();
}

function setItemSelected(item, selected) {
  if (matchesAllCriteria(item)) {
    selected ? state.excludedIds.delete(item.id) : state.excludedIds.add(item.id);
  } else {
    selected ? state.selectedIds.add(item.id) : state.selectedIds.delete(item.id);
  }
}

function setIdSelected(id, selected, belongsToAllSelection = false) {
  if (state.selectionAll && belongsToAllSelection) {
    state.selectedIds.delete(id);
    selected ? state.excludedIds.delete(id) : state.excludedIds.add(id);
  } else {
    state.excludedIds.delete(id);
    selected ? state.selectedIds.add(id) : state.selectedIds.delete(id);
  }
}

async function selectRange(item, selected) {
  if (!state.lastSelectedId) {
    setItemSelected(item, selected);
    state.lastSelectedId = item.id;
    updateSelectionUI();
    return;
  }
  const result = await jsonRequest("/api/catalog-range", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      anchor: state.lastSelectedId, target: item.id,
      query: state.query, kind: state.kind, sort: state.sort,
      selection_query: state.allCriteria?.query || "",
      selection_kind: state.allCriteria?.kind || "both",
    }),
  });
  const matchingAll = new Set(state.selectionAll ? result.matching_selection_ids : []);
  result.ids.forEach(id => setIdSelected(id, selected, matchingAll.has(id)));
  updateSelectionUI();
}

async function handleCardSelection(item, event, toggleOnly = false) {
  try {
    if (event.shiftKey) {
      await selectRange(item, !isSelected(item));
      return;
    }
    if (event.metaKey || event.ctrlKey || toggleOnly) {
      setItemSelected(item, !isSelected(item));
    } else {
      state.selectionAll = false;
      state.allCriteria = null;
      state.selectedIds.clear();
      state.excludedIds.clear();
      setItemSelected(item, true);
    }
    state.lastSelectedId = item.id;
    updateSelectionUI();
  } catch (error) {
    toast(error.message, { error: true });
  }
}

function selectionPayload() {
  if (state.selectionAll) {
    return {
      mode: "all", query: state.allCriteria.query, kind: state.allCriteria.kind,
      excluded: [...state.excludedIds], included: [...state.selectedIds],
    };
  }
  return { mode: "ids", ids: [...state.selectedIds] };
}

function updateSelectionUI() {
  if (!state.catalog) return;
  const count = selectedCount();
  bulkBar.hidden = count === 0;
  document.body.classList.toggle("selection-active", count > 0);
  document.querySelector("#bulk-count").textContent = `${count.toLocaleString()} selected`;
  const pageItems = state.catalog.items;
  const pageSelected = pageItems.length > 0 && pageItems.every(isSelected);
  selectPage.textContent = pageSelected ? "Deselect page" : "Select all on page";
  selectAll.textContent = state.selectionAll ? "Clear all results" : `Select all ${state.catalog.filtered_total.toLocaleString()} results`;
  document.querySelectorAll(".card").forEach(card => {
    const item = pageItems.find(candidate => candidate.id === card.dataset.id);
    const selected = item ? isSelected(item) : false;
    card.classList.toggle("selected", selected);
    const checkbox = card.querySelector(".card-checkbox");
    if (checkbox) checkbox.checked = selected;
  });
}

function renderBulkActions() {
  const actions = state.catalog?.actions || [];
  bulkActions.innerHTML = `${actions.slice(0, 2).map(action => actionButtonMarkup(action, "bulk-move")).join("")}${overflowMarkup(actions.slice(2), "bulk-overflow")}`;
}

function updateSummary() {
  const result = state.catalog;
  const visible = result.filtered_total === result.total ? `${result.total} items` : `${result.filtered_total} of ${result.total}`;
  summary.textContent = `${visible} · ${result.pictures} pics · ${result.videos} videos`;
  pageNumber.value = String(result.page);
  pageNumber.max = String(result.pages);
  pageTotal.textContent = result.pages.toLocaleString();
  previousPage.disabled = result.page <= 1;
  nextPage.disabled = result.page >= result.pages;
  document.querySelector("#pagination").hidden = result.filtered_total === 0;
}

function cardMarkup(item, index) {
  const selected = isSelected(item);
  const thumb = `<img class="poster" src="${escapeHtml(item.thumbnail_url)}" alt="Thumbnail for ${escapeHtml(item.name)}" loading="lazy">`;
  const play = item.kind === "video" ? `<button class="play-here" type="button" aria-label="Play ${escapeHtml(item.name)} here" title="Play here"></button>` : "";
  const verb = item.kind === "video" ? "Play in new tab" : "Open photo";
  const actions = state.catalog.actions || [];
  const directActions = actions.slice(0, 2).map(action => actionButtonMarkup(action)).join("");
  const moreActions = overflowMarkup(actions.slice(2));
  return `<article class="card ${selected ? "selected" : ""}" data-id="${escapeHtml(item.id)}" style="animation-delay:${Math.min(index, 12) * 18}ms">
    <div class="preview"><a class="preview-link" href="${escapeHtml(item.viewer_url)}" target="_blank" rel="noopener" aria-label="Open ${escapeHtml(item.name)} in a new tab">${thumb}</a>${play}<span class="kind-badge">${item.kind === "video" ? "Video" : "Pic"}</span><label class="card-select" title="Select ${escapeHtml(item.name)}"><input class="card-checkbox" type="checkbox" ${selected ? "checked" : ""} aria-label="Select ${escapeHtml(item.name)}"></label></div>
    <div class="card-body"><h2 class="name" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</h2><p class="folder" title="${escapeHtml(item.folder)}">${escapeHtml(item.folder || state.catalog.source_label)}</p><div class="metadata"><span>${escapeHtml(item.size_label)}</span><span>${escapeHtml(item.modified_label)}</span></div>
      <div class="actions"><div class="action-row"><a class="action primary" href="${escapeHtml(item.viewer_url)}" target="_blank" rel="noopener">↗ ${verb}</a><button class="action secondary reveal" type="button">Finder</button></div><div class="action-row file-row destination-actions">${directActions}${moreActions}</div></div>
    </div></article>`;
}

function stopActivePlayer() {
  if (!state.active) return;
  state.active.video.pause();
  if (state.active.card.isConnected) state.active.card.querySelector(".preview").innerHTML = state.active.original;
  state.active = null;
}

function render() {
  if (!state.catalog) return;
  stopActivePlayer();
  const items = state.catalog.items;
  let emptyMessage = "No media matches this view.";
  if (state.kind === "picture" && state.catalog.media_mode === "videos") emptyMessage = `Pictures are not in the current catalog. <button class="button empty-settings" type="button">Change Settings</button>`;
  if (state.kind === "video" && state.catalog.media_mode === "pictures") emptyMessage = `Videos are not in the current catalog. <button class="button empty-settings" type="button">Change Settings</button>`;
  gallery.innerHTML = items.length ? items.map(cardMarkup).join("") : `<div class="empty">${emptyMessage}</div>`;
  renderBulkActions();
  updateSummary();
  updateSelectionUI();
}

function captureGalleryTransition(removedIds) {
  const positions = new Map();
  const affectedRows = new Set();
  document.querySelectorAll(".card").forEach(card => {
    const rect = card.getBoundingClientRect();
    positions.set(card.dataset.id, rect);
    if (removedIds.has(card.dataset.id)) affectedRows.add(Math.round(rect.top));
  });
  return { positions, affectedRows, removedIds };
}

async function fadeDepartures(transition) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const animations = [...document.querySelectorAll(".card")]
    .filter(card => transition.removedIds.has(card.dataset.id))
    .map(card => {
      card.classList.add("departing");
      return card.animate(
        [{ opacity: 1, transform: "scale(1)" }, { opacity: 0, transform: "scale(.965)" }],
        { duration: 180, easing: "cubic-bezier(.4,0,1,1)", fill: "forwards" },
      ).finished.catch(() => {});
    });
  await Promise.all(animations);
}

async function animateGalleryTransition(transition) {
  if (!transition || matchMedia("(prefers-reduced-motion: reduce)").matches) {
    gallery.classList.remove("reflowing");
    return;
  }
  const animations = [];
  document.querySelectorAll(".card").forEach(card => {
    const before = transition.positions.get(card.dataset.id);
    const after = card.getBoundingClientRect();
    if (before && transition.affectedRows.has(Math.round(before.top))) {
      const x = before.left - after.left;
      const y = before.top - after.top;
      animations.push(card.animate(
        [{ opacity: .7, transform: `translate(${x}px,${y}px)` }, { opacity: 1, transform: "translate(0,0)" }],
        { duration: 300, easing: "cubic-bezier(.2,.75,.2,1)" },
      ).finished.catch(() => {}));
    } else {
      animations.push(card.animate(
        [{ opacity: .28, transform: "translateY(5px)" }, { opacity: 1, transform: "translateY(0)" }],
        { duration: 240, easing: "ease-out" },
      ).finished.catch(() => {}));
    }
  });
  await Promise.all(animations);
  document.querySelectorAll(".card").forEach(card => { card.style.animation = "none"; });
  gallery.classList.remove("reflowing");
}

async function jsonRequest(url, options = {}) {
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "The request failed");
  return result;
}

async function loadCatalog(announce = false, transition = null) {
  const requestNumber = ++state.requestNumber;
  const parameters = new URLSearchParams({
    page: String(state.page), page_size: String(state.pageSize), query: state.query,
    kind: state.kind, sort: state.sort,
  });
  try {
    const result = await jsonRequest(`/api/catalog?${parameters}`);
    if (requestNumber !== state.requestNumber) return;
    state.catalog = result;
    state.page = result.page;
    title.textContent = result.title;
    document.title = `${result.title} · SlideSorter`;
    if (transition) gallery.classList.add("reflowing");
    render();
    await animateGalleryTransition(transition);
    if (announce) toast("Gallery refreshed");
  } catch (error) {
    if (requestNumber !== state.requestNumber) return;
    gallery.classList.remove("reflowing");
    gallery.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    toast(error.message, { error: true });
  }
}

async function updateUndoState() {
  try { undoLast.disabled = !(await jsonRequest("/api/history?limit=1")).can_undo; }
  catch { undoLast.disabled = true; }
}

function playHere(card, item) {
  stopActivePlayer();
  const preview = card.querySelector(".preview");
  const original = preview.innerHTML;
  const player = document.createElement("video");
  player.className = "inline-video";
  player.src = item.media_url;
  player.controls = true;
  player.playsInline = true;
  player.preload = "metadata";
  preview.replaceChildren(player);
  state.active = { card, video: player, original };
  player.addEventListener("ended", () => {
    if (state.active?.video === player) {
      stopActivePlayer();
      updateSelectionUI();
    }
  });
  player.play().catch(() => toast("Playback is ready; use the video controls", { error: true }));
}

async function undo(token = null) {
  try {
    const body = token ? { token } : {};
    const result = await jsonRequest("/api/undo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    await loadCatalog();
    await updateUndoState();
    toast(result.warning || `${result.name} restored to ${result.count === 1 ? "its" : "their"} original location`, { thumbnail: result.thumbnail_url, error: Boolean(result.warning) });
  } catch (error) { toast(error.message, { error: true }); }
}

async function performMove(action, item, button, card) {
  closeActionMenus();
  button.disabled = true;
  const transition = captureGalleryTransition(new Set([item.id]));
  try {
    const result = await jsonRequest("/api/move", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: item.id, action_id: action.id }) });
    await fadeDepartures(transition);
    if (isSelected(item)) setItemSelected(item, false);
    await loadCatalog(false, transition);
    undoLast.disabled = false;
    toast(result.warning || `${item.name} moved to ${result.destination_label || action.display_label}`, {
      error: Boolean(result.warning), thumbnail: result.thumbnail_url,
      actionLabel: "Undo", onAction: () => undo(result.token), duration: 12000,
    });
  } catch (error) {
    button.disabled = false;
    toast(error.message, { error: true });
  }
}

async function performBulkMove(action) {
  closeActionMenus();
  const count = selectedCount();
  if (!count) return;
  const buttons = [...bulkActions.querySelectorAll("button")];
  const visibleSelected = new Set((state.catalog?.items || []).filter(isSelected).map(item => item.id));
  const transition = captureGalleryTransition(visibleSelected);
  buttons.forEach(button => { button.disabled = true; });
  try {
    const result = await jsonRequest("/api/bulk-move", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selection: selectionPayload(), action_id: action.id }),
    });
    await fadeDepartures(transition);
    clearSelection();
    await loadCatalog(false, transition);
    await updateUndoState();
    toast(result.warning || `${result.count.toLocaleString()} items moved to ${result.destination_label || action.display_label}`, {
      error: Boolean(result.warning), thumbnail: result.thumbnail_url,
      actionLabel: "Undo", onAction: () => undo(result.token), duration: 15000,
    });
  } catch (error) {
    toast(error.message, { error: true, duration: 12000 });
  } finally {
    buttons.forEach(button => { button.disabled = false; });
  }
}

async function refreshCatalog() {
  const button = document.querySelector("#refresh");
  button.disabled = true;
  button.textContent = "Refreshing…";
  try {
    await jsonRequest("/api/refresh", { method: "POST" });
    state.page = 1;
    await loadCatalog(true);
    await updateUndoState();
  } catch (error) { toast(error.message, { error: true }); }
  finally { button.disabled = false; button.textContent = "Refresh"; }
}

function closeSettings() {
  sheet.classList.remove("open");
  sheet.setAttribute("aria-hidden", "true");
  scrim.hidden = true;
  document.querySelector("#settings-open").focus();
}

function newActionId() {
  return `action-${crypto.randomUUID().replaceAll("-", "")}`;
}

function destinationRowMarkup(action) {
  const presentation = action.display_label ? action : actionPresentation(action.label);
  return `<article class="destination-row" data-action-id="${escapeHtml(action.id || newActionId())}">
    <div class="destination-row-head"><span class="destination-order"></span><span class="destination-preview tone-${escapeHtml(presentation.tone)}">${iconMarkup(presentation.icon)}<strong>${escapeHtml(presentation.display_label)}</strong></span><div class="destination-order-actions"><button class="mini-button destination-up" type="button" aria-label="Move destination up">↑</button><button class="mini-button destination-down" type="button" aria-label="Move destination down">↓</button><button class="mini-button destination-delete" type="button" aria-label="Remove destination">×</button></div></div>
    <label class="compact-field"><span>Button label</span><input class="destination-label" value="${escapeHtml(action.label || "")}" maxlength="120" placeholder="Review later (blue clock icon)" required></label>
    <label class="compact-field"><span>Destination folder</span><span class="path-control"><input class="destination-root" value="${escapeHtml(action.root || "")}" required><button class="choose" type="button" data-choose="action_root">Choose…</button></span></label>
  </article>`;
}

function refreshDestinationRows() {
  const rows = [...destinationList.querySelectorAll(".destination-row")];
  rows.forEach((row, index) => {
    row.querySelector(".destination-order").textContent = String(index + 1).padStart(2, "0");
    row.querySelector(".destination-up").disabled = index === 0;
    row.querySelector(".destination-down").disabled = index === rows.length - 1;
    row.querySelector(".destination-delete").disabled = rows.length === 1;
    const presentation = actionPresentation(row.querySelector(".destination-label").value);
    const preview = row.querySelector(".destination-preview");
    preview.className = `destination-preview tone-${presentation.tone}`;
    preview.innerHTML = `${iconMarkup(presentation.icon)}<strong>${escapeHtml(presentation.display_label)}</strong>`;
  });
}

function renderDestinationEditor(actions) {
  destinationList.innerHTML = actions.map(destinationRowMarkup).join("");
  refreshDestinationRows();
}

function collectDestinationActions() {
  return [...destinationList.querySelectorAll(".destination-row")].map(row => ({
    id: row.dataset.actionId,
    label: row.querySelector(".destination-label").value.trim(),
    root: row.querySelector(".destination-root").value.trim(),
  }));
}

async function openSettings() {
  try {
    const config = await jsonRequest("/api/settings");
    document.querySelector("#media-root").value = config.media_root;
    renderDestinationEditor(config.actions);
    document.querySelector("#keep-structure").checked = config.keep_structure !== false;
    document.querySelector("#media-mode").value = config.media_mode;
    document.querySelector("#gallery-title").value = config.title;
    document.querySelector("#source-label").value = config.source_label;
    document.querySelector("#page-capacity").value = String(state.pageSize);
    scrim.hidden = false;
    sheet.classList.add("open");
    sheet.setAttribute("aria-hidden", "false");
    document.querySelector("#media-root").focus();
  } catch (error) { toast(error.message, { error: true }); }
}

async function chooseDirectory(button) {
  button.disabled = true;
  try {
    const result = await jsonRequest("/api/choose-directory", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ field: button.dataset.choose }) });
    const target = button.dataset.choose === "media_root"
      ? document.querySelector("#media-root")
      : button.closest(".destination-row").querySelector(".destination-root");
    target.value = result.path;
  } catch (error) {
    if (error.message !== "No folder selected") toast(error.message, { error: true });
  } finally { button.disabled = false; }
}

function changePage(page) {
  state.page = page;
  loadCatalog();
  window.scrollTo({ top: Math.max(0, gallery.offsetTop - 170), behavior: "smooth" });
}

function goToEnteredPage() {
  const maximum = state.catalog?.pages || 1;
  const entered = Number.parseInt(pageNumber.value, 10);
  const target = Number.isFinite(entered) ? Math.max(1, Math.min(maximum, entered)) : state.page;
  pageNumber.value = String(target);
  if (target !== state.page) changePage(target);
}

function configuredAction(actionId) {
  return state.catalog?.actions?.find(action => action.id === actionId);
}

function closeActionMenus(except = null) {
  document.querySelectorAll(".action-menu-wrap.open").forEach(wrapper => {
    if (wrapper === except) return;
    wrapper.classList.remove("open");
    wrapper.querySelector(".action-menu").hidden = true;
    wrapper.querySelector(".more-actions").setAttribute("aria-expanded", "false");
  });
}

function toggleActionMenu(button) {
  const wrapper = button.closest(".action-menu-wrap");
  const opening = !wrapper.classList.contains("open");
  closeActionMenus(wrapper);
  wrapper.classList.toggle("open", opening);
  wrapper.querySelector(".action-menu").hidden = !opening;
  button.setAttribute("aria-expanded", String(opening));
}

gallery.addEventListener("click", event => {
  if (event.target.closest(".empty-settings")) { openSettings(); return; }
  const card = event.target.closest(".card");
  if (!card || !state.catalog) return;
  const item = state.catalog.items.find(candidate => candidate.id === card.dataset.id);
  if (!item) return;
  if (event.target.closest(".card-select")) {
    event.preventDefault();
    handleCardSelection(item, event, true);
    return;
  }
  if (event.target.closest(".play-here")) { playHere(card, item); return; }
  if (event.target.closest(".reveal")) { jsonRequest("/api/reveal", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: item.id }) }).catch(error => toast(error.message, { error: true })); return; }
  const more = event.target.closest(".more-actions");
  if (more) { toggleActionMenu(more); return; }
  const move = event.target.closest(".move-action");
  if (move) {
    const action = configuredAction(move.dataset.actionId);
    if (action) performMove(action, item, move, card);
    return;
  }
  if (event.target.closest("a")) {
    if (event.metaKey || event.ctrlKey || event.shiftKey) {
      event.preventDefault();
      handleCardSelection(item, event);
    }
    return;
  }
  handleCardSelection(item, event);
});

let searchTimer;
search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { state.query = search.value; state.page = 1; state.lastSelectedId = null; loadCatalog(); }, 250);
});
sort.addEventListener("change", () => { state.sort = sort.value; state.page = 1; loadCatalog(); });
document.querySelector("#kind-switch").addEventListener("click", event => {
  const button = event.target.closest("[data-kind]");
  if (!button) return;
  state.kind = button.dataset.kind;
  state.page = 1;
  state.lastSelectedId = null;
  document.querySelectorAll(".kind-option").forEach(option => option.classList.toggle("active", option === button));
  loadCatalog();
});
pageSize.addEventListener("change", () => {
  state.pageSize = Math.max(25, Math.min(500, Math.round(Number(pageSize.value || 100) / 25) * 25));
  pageSize.value = String(state.pageSize);
  state.page = 1;
  localStorage.setItem("media-gallery-page-size", String(state.pageSize));
  loadCatalog();
});
previousPage.addEventListener("click", () => changePage(Math.max(1, state.page - 1)));
nextPage.addEventListener("click", () => changePage(state.page + 1));
pageNumber.addEventListener("change", goToEnteredPage);
pageNumber.addEventListener("keydown", event => {
  if (event.key === "Enter") { event.preventDefault(); goToEnteredPage(); pageNumber.blur(); }
  if (event.key === "Escape") { pageNumber.value = String(state.page); pageNumber.blur(); }
});
selectPage.addEventListener("click", () => {
  const items = state.catalog?.items || [];
  const shouldSelect = !items.length || !items.every(isSelected);
  items.forEach(item => setItemSelected(item, shouldSelect));
  updateSelectionUI();
});
selectAll.addEventListener("click", () => {
  if (state.selectionAll) { clearSelection(); return; }
  if (!state.catalog?.filtered_total) return;
  state.selectionAll = true;
  state.allCriteria = { query: state.query, kind: state.kind, total: state.catalog.filtered_total };
  state.selectedIds.clear();
  state.excludedIds.clear();
  state.lastSelectedId = null;
  updateSelectionUI();
});
document.querySelector("#bulk-clear").addEventListener("click", clearSelection);
bulkActions.addEventListener("click", event => {
  const more = event.target.closest(".more-actions");
  if (more) { toggleActionMenu(more); return; }
  const move = event.target.closest(".move-action");
  if (!move) return;
  const action = configuredAction(move.dataset.actionId);
  if (action) performBulkMove(action);
});
document.querySelector("#refresh").addEventListener("click", refreshCatalog);
undoLast.addEventListener("click", () => undo());
document.querySelector("#settings-open").addEventListener("click", openSettings);
document.querySelector("#settings-close").addEventListener("click", closeSettings);
document.querySelector("#settings-cancel").addEventListener("click", closeSettings);
scrim.addEventListener("click", closeSettings);
document.querySelector("#settings-form").addEventListener("click", event => {
  const choose = event.target.closest(".choose");
  if (choose) { chooseDirectory(choose); return; }
  const row = event.target.closest(".destination-row");
  if (!row) return;
  if (event.target.closest(".destination-up") && row.previousElementSibling) {
    destinationList.insertBefore(row, row.previousElementSibling);
    refreshDestinationRows();
  } else if (event.target.closest(".destination-down") && row.nextElementSibling) {
    destinationList.insertBefore(row.nextElementSibling, row);
    refreshDestinationRows();
  } else if (event.target.closest(".destination-delete") && destinationList.children.length > 1) {
    row.remove();
    refreshDestinationRows();
  }
});
destinationList.addEventListener("input", event => {
  if (event.target.matches(".destination-label")) refreshDestinationRows();
});
document.querySelector("#destination-add").addEventListener("click", () => {
  destinationList.insertAdjacentHTML("beforeend", destinationRowMarkup({ id: newActionId(), label: "Review later (blue clock icon)", root: "" }));
  refreshDestinationRows();
  destinationList.querySelector(".destination-row:last-child .destination-label").focus();
});
document.querySelector("#settings-form").addEventListener("submit", async event => {
  event.preventDefault();
  const save = document.querySelector("#settings-save");
  save.disabled = true;
  save.textContent = "Rebuilding…";
  try {
    const form = new FormData(event.currentTarget);
    const settings = Object.fromEntries(form);
    settings.actions = collectDestinationActions();
    settings.keep_structure = document.querySelector("#keep-structure").checked;
    const requestedPageSize = Math.max(25, Math.min(500, Math.round(Number(settings.page_capacity || 100) / 25) * 25));
    delete settings.page_capacity;
    await jsonRequest("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(settings) });
    state.pageSize = requestedPageSize;
    pageSize.value = String(requestedPageSize);
    localStorage.setItem("media-gallery-page-size", String(requestedPageSize));
    closeSettings();
    state.kind = "both";
    state.page = 1;
    document.querySelectorAll(".kind-option").forEach(option => option.classList.toggle("active", option.dataset.kind === "both"));
    await loadCatalog();
    await updateUndoState();
    toast("Settings saved and catalog rebuilt");
  } catch (error) { toast(error.message, { error: true, duration: 12000 }); }
  finally { save.disabled = false; save.textContent = "Save & rebuild"; }
});

document.addEventListener("keydown", event => {
  if (event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey && !event.target.matches("input,textarea,select")) { event.preventDefault(); search.focus(); }
  if (event.key === "Escape" && sheet.classList.contains("open")) closeSettings();
  if (event.key === "Escape") closeActionMenus();
  if (event.code === "Space" && state.active && !event.target.matches("input,textarea,button,a,select")) { event.preventDefault(); state.active.video.paused ? state.active.video.play() : state.active.video.pause(); }
});

document.addEventListener("click", event => {
  if (!event.target.closest(".action-menu-wrap")) closeActionMenus();
});

Promise.all([loadCatalog(), updateUndoState()]);
