const galleryReturnKey = "slidesorter-gallery-return";
const galleryRestoreKey = "slidesorter-gallery-restore";
const gallerySelectionPrefix = "slidesorter-gallery-selection:";
const galleryThumbnailSizePrefix = "slidesorter-gallery-thumbnail-size:";
const defaultThumbnailSize = 280;
const reservedShortcuts = new Set(["u"]);
const galleryLocation = new URL(location.href);
const returnedSelectionToken = galleryLocation.searchParams.get("return_token");
let restoredSelection = null;
if (returnedSelectionToken && /^[a-z0-9-]{8,}$/i.test(returnedSelectionToken)) {
  try { restoredSelection = JSON.parse(localStorage.getItem(`${gallerySelectionPrefix}${returnedSelectionToken}`) || "null"); }
  catch { restoredSelection = null; }
  galleryLocation.searchParams.delete("return_token");
  history.replaceState(null, "", `${galleryLocation.pathname}${galleryLocation.search}${galleryLocation.hash}`);
}
const savedPageSize = Number(localStorage.getItem("media-gallery-page-size"));
let restoredView = null;
if (sessionStorage.getItem(galleryRestoreKey) === "1") {
  try { restoredView = JSON.parse(sessionStorage.getItem(galleryReturnKey) || "null"); }
  catch { restoredView = null; }
  sessionStorage.removeItem(galleryRestoreKey);
}
if (restoredView && "scrollRestoration" in history) history.scrollRestoration = "manual";
const restoredPageSize = Number(restoredView?.pageSize);
const initialPageSize = restoredPageSize >= 25 && restoredPageSize <= 500 && restoredPageSize % 25 === 0
  ? restoredPageSize
  : (savedPageSize >= 25 && savedPageSize <= 500 && savedPageSize % 25 === 0 ? savedPageSize : 100);
const restoredSort = ["oldest", "newest", "name", "size"].includes(restoredView?.sort) ? restoredView.sort : "oldest";
const restoredKind = ["both", "picture", "video"].includes(restoredView?.kind) ? restoredView.kind : "both";
const state = {
  catalog: null, query: typeof restoredView?.query === "string" ? restoredView.query : "", sort: restoredSort, kind: restoredKind, active: null,
  page: Math.max(1, Number.parseInt(restoredView?.page, 10) || 1), pageSize: initialPageSize,
  requestNumber: 0, selectionAll: false, allCriteria: null,
  selectedIds: new Set(), excludedIds: new Set(), lastSelectedId: null,
  activeTileId: null, popoverItemId: null,
  selectionToken: returnedSelectionToken || crypto.randomUUID(),
  appearance: "system", collectionRoot: null, collectionPending: null, collectionActions: [], bulkMoving: false,
  thumbnailSize: defaultThumbnailSize, thumbnailRoot: null,
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
const bulkActions = document.querySelector("#bulk-actions");
const thumbnailSize = document.querySelector("#thumbnail-size");
const itemActionPopover = document.querySelector("#item-action-popover");
const pageNumber = document.querySelector("#page-number");
const pageTotal = document.querySelector("#page-total");
const destinationList = document.querySelector("#destination-list");
pageSize.value = String(state.pageSize);
search.value = state.query;
sort.value = state.sort;
document.querySelectorAll(".kind-option").forEach(option => option.classList.toggle("active", option.dataset.kind === state.kind));

function normalizedThumbnailSize(value) {
  return Math.max(160, Math.min(440, Math.round(Number(value || defaultThumbnailSize) / 10) * 10));
}

function applyThumbnailSize(value, persist = true) {
  state.thumbnailSize = normalizedThumbnailSize(value);
  document.documentElement.style.setProperty("--thumbnail-size", `${state.thumbnailSize}px`);
  document.documentElement.style.setProperty("--gallery-gap", `${Math.round(8 + (state.thumbnailSize - 160) * .055)}px`);
  thumbnailSize.value = String(state.thumbnailSize);
  if (persist && state.catalog?.media_root) {
    localStorage.setItem(`${galleryThumbnailSizePrefix}${state.catalog.media_root}`, String(state.thumbnailSize));
  }
}

let thumbnailResizeFrame = null;
let pendingThumbnailSize = defaultThumbnailSize;
let thumbnailResizeTimer = null;

function animateThumbnailSize(value) {
  pendingThumbnailSize = normalizedThumbnailSize(value);
  if (thumbnailResizeFrame !== null) return;
  thumbnailResizeFrame = requestAnimationFrame(() => {
    thumbnailResizeFrame = null;
    applyThumbnailSize(pendingThumbnailSize);
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    gallery.classList.add("size-settling");
    clearTimeout(thumbnailResizeTimer);
    thumbnailResizeTimer = setTimeout(() => {
      gallery.classList.remove("size-settling");
    }, 160);
  });
}

function restoreThumbnailSize(root) {
  const saved = Number(localStorage.getItem(`${galleryThumbnailSizePrefix}${root}`));
  applyThumbnailSize(saved || defaultThumbnailSize, false);
}

applyThumbnailSize(defaultThumbnailSize, false);

const escapeHtml = value => String(value).replace(/[&<>'"]/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[character]);

function restoreScrollPosition(value) {
  const scrollY = Math.max(0, Number(value) || 0);
  let observer = null;
  let timeout = null;
  const apply = () => {
    window.scrollTo(0, scrollY);
    observer?.disconnect();
    if (timeout) clearTimeout(timeout);
  };
  const applyWhenReady = () => {
    const maxScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    if (maxScroll + 1 < scrollY) return false;
    apply();
    return true;
  };
  requestAnimationFrame(() => {
    if (applyWhenReady()) return;
    if ("ResizeObserver" in window) {
      observer = new ResizeObserver(applyWhenReady);
      observer.observe(document.body);
    }
    timeout = setTimeout(apply, 1500);
  });
}

const iconPaths = {
  trash: '<path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5m4-5v5"/>',
  tray: '<path d="M12 15V3m0 0L7 8m5-5 5 5M4 14v6h16v-6"/>',
  archive: '<path d="M4 7h16v13H4zM3 4h18v3H3zm6 8h6"/>',
  folder: '<path d="M3.5 6.5h6l2 2h9v9.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M3.5 8.5h17"/>',
  star: '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9z"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  tag: '<path d="m20 13-7 7-9-9V4h7z"/><circle cx="8.5" cy="8.5" r="1"/>',
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

function shortcutInitial(action) {
  return [...String(action?.display_label || action?.label || "")].find(character => /[\p{L}\p{N}]/u.test(character))?.toLocaleLowerCase() || "";
}

function normalizedShortcut(value) {
  const shortcut = String(value || "").trim();
  return [...shortcut].length === 1 && /[\p{L}\p{N}]/u.test(shortcut) ? shortcut.toLocaleLowerCase() : "";
}

function suggestedShortcutForAction(action, actions = []) {
  const configured = normalizedShortcut(action?.shortcut);
  if (configured && !reservedShortcuts.has(configured)) return configured;
  const initial = shortcutInitial(action);
  if (!initial || reservedShortcuts.has(initial)) return "";
  const matchingLabels = actions.filter(candidate => shortcutInitial(candidate) === initial).length;
  const claimed = actions.some(candidate => normalizedShortcut(candidate?.shortcut) === initial);
  return matchingLabels === 1 && !claimed ? initial : "";
}

function shortcutForAction(action) {
  return suggestedShortcutForAction(action, state.catalog?.actions || []);
}

function actionShortcutMarkup(action, showShortcut) {
  const key = showShortcut ? shortcutForAction(action) : "";
  return key ? `<kbd class="action-shortcut" title="Shortcut: ${escapeHtml(key.toUpperCase())}">${escapeHtml(key.toUpperCase())}</kbd>` : "";
}

function actionButtonMarkup(action, extraClass = "", showShortcut = false, customTitle = "") {
  const key = showShortcut ? shortcutForAction(action) : "";
  const title = customTitle || (key ? `Move to ${action.display_label} · shortcut ${key.toUpperCase()}` : `Move to ${action.display_label}`);
  return `<button class="action move-action tone-${escapeHtml(action.tone)} ${extraClass}" type="button" data-action-id="${escapeHtml(action.id)}" title="${escapeHtml(title)}">${iconMarkup(action.icon)}<span>${escapeHtml(action.display_label)}</span>${actionShortcutMarkup(action, showShortcut)}</button>`;
}

function overflowMarkup(actions, extraClass = "", showShortcut = false) {
  if (!actions.length) return "";
  return `<div class="action-menu-wrap ${extraClass}"><button class="action more-actions" type="button" aria-haspopup="menu" aria-expanded="false">More <span aria-hidden="true">⌄</span></button><div class="action-menu" role="menu" hidden>${actions.map(action => `<button class="action-menu-item move-action tone-${escapeHtml(action.tone)}" type="button" role="menuitem" data-action-id="${escapeHtml(action.id)}">${iconMarkup(action.icon)}<span>${escapeHtml(action.display_label)}</span>${actionShortcutMarkup(action, showShortcut)}</button>`).join("")}</div></div>`;
}

let bulkActionLayoutFrame = null;

function renderBulkActions(actions) {
  bulkActions.innerHTML = actions.map(action => actionButtonMarkup(action, "", true)).join("");
  if (!actions.length || bulkBar.hidden) return;
  if (bulkActionLayoutFrame !== null) cancelAnimationFrame(bulkActionLayoutFrame);
  bulkActionLayoutFrame = requestAnimationFrame(() => fitBulkActions(actions));
}

function fitBulkActions(actions) {
  bulkActionLayoutFrame = null;
  if (bulkBar.hidden || !actions.length) return;
  const gap = Number.parseFloat(getComputedStyle(bulkActions).gap) || 8;
  const widths = [...bulkActions.querySelectorAll(":scope > .move-action")].map(button => button.getBoundingClientRect().width);
  const available = bulkActions.clientWidth;
  if (!available || widths.reduce((sum, width) => sum + width, 0) + Math.max(0, widths.length - 1) * gap <= available) return;

  bulkActions.innerHTML = actions.map(action => actionButtonMarkup(action, "", true)).join("")
    + overflowMarkup([actions.at(-1)], "bulk-overflow", true);
  const moreWidth = bulkActions.querySelector(".more-actions").getBoundingClientRect().width;
  let visible = 0;
  let used = 0;
  for (let index = 0; index < actions.length - 1; index += 1) {
    const next = used + (visible ? gap : 0) + widths[index];
    if (next + gap + moreWidth > available) break;
    used = next;
    visible += 1;
  }
  visible = Math.max(1, visible);
  bulkActions.innerHTML = actions.slice(0, visible).map(action => actionButtonMarkup(action, "", true)).join("")
    + overflowMarkup(actions.slice(visible), "bulk-overflow", true);
}

function tintCardFromPoster(card, image) {
  if (!image.naturalWidth || card.dataset.tinted) return;
  try {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 4;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    context.drawImage(image, 0, 0, 4, 4);
    const pixels = context.getImageData(0, 0, 4, 4).data;
    let red = 0; let green = 0; let blue = 0; let count = 0;
    for (let index = 0; index < pixels.length; index += 4) {
      if (pixels[index + 3] < 128) continue;
      red += pixels[index]; green += pixels[index + 1]; blue += pixels[index + 2]; count += 1;
    }
    if (!count) return;
    card.style.setProperty("--card-tint", `${Math.round(red / count)} ${Math.round(green / count)} ${Math.round(blue / count)}`);
    card.dataset.tinted = "true";
  } catch { /* A poster that cannot be sampled keeps the neutral card tone. */ }
}

function applyCardTints() {
  gallery.querySelectorAll(".card .poster").forEach(image => {
    const card = image.closest(".card");
    if (!card) return;
    if (image.complete) tintCardFromPoster(card, image);
    else image.addEventListener("load", () => tintCardFromPoster(card, image), { once: true });
  });
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

function persistSelection() {
  const key = `${gallerySelectionPrefix}${state.selectionToken}`;
  if (!selectedCount() || !state.catalog?.media_root) {
    localStorage.removeItem(key);
    return;
  }
  localStorage.setItem(key, JSON.stringify({
    mediaRoot: state.catalog.media_root,
    selectionAll: state.selectionAll,
    allCriteria: state.allCriteria,
    selectedIds: [...state.selectedIds],
    excludedIds: [...state.excludedIds],
    lastSelectedId: state.lastSelectedId,
  }));
}

function restoreSelectionForCatalog() {
  const snapshot = restoredSelection;
  restoredSelection = null;
  if (!snapshot || snapshot.mediaRoot !== state.catalog?.media_root) return;
  state.selectionAll = snapshot.selectionAll === true;
  state.allCriteria = state.selectionAll && snapshot.allCriteria && typeof snapshot.allCriteria === "object"
    ? snapshot.allCriteria : null;
  state.selectedIds = new Set(Array.isArray(snapshot.selectedIds) ? snapshot.selectedIds.filter(id => typeof id === "string") : []);
  state.excludedIds = new Set(Array.isArray(snapshot.excludedIds) ? snapshot.excludedIds.filter(id => typeof id === "string") : []);
  state.lastSelectedId = typeof snapshot.lastSelectedId === "string" ? snapshot.lastSelectedId : null;
  if (!state.allCriteria) state.selectionAll = false;
}

function viewerUrl(item) {
  if (!selectedCount()) return item.viewer_url;
  const url = new URL(item.viewer_url, location.origin);
  url.searchParams.set("return_token", state.selectionToken);
  return `${url.pathname}${url.search}`;
}

function singleSelectedItem() {
  if (selectedCount() !== 1) return null;
  return state.catalog?.items.find(isSelected) || null;
}

function openSingleSelectedItem() {
  const item = singleSelectedItem();
  if (!item) return;
  window.open(viewerUrl(item), "_blank", "noopener");
  toast(`Opened ${item.name}`);
}

function revealSingleSelectedItem() {
  const item = singleSelectedItem();
  if (!item) return;
  jsonRequest("/api/reveal", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: item.id }),
  }).then(() => toast(`Revealed ${item.name} in Finder`)).catch(error => toast(error.message, { error: true }));
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
  if (count > 0) {
    closeItemActionPopover();
    setActiveTile(null);
  }
  bulkBar.hidden = count === 0;
  document.body.classList.toggle("selection-active", count > 0);
  if (count === 0) document.body.classList.remove("selection-top-revealed");
  document.querySelector("#bulk-count").textContent = `${count.toLocaleString()} selected`;
  const actions = state.catalog.actions || [];
  renderBulkActions(actions);
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
    if (item) card.querySelectorAll(".viewer-link").forEach(link => { link.href = viewerUrl(item); });
  });
  persistSelection();
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

function setActiveTile(card) {
  const target = selectedCount() === 0 && card?.classList.contains("card") ? card : null;
  state.activeTileId = target?.dataset.id || null;
  document.querySelectorAll(".card.shortcut-target").forEach(candidate => candidate.classList.toggle("shortcut-target", candidate === target));
}

function setPopoverTarget(card) {
  const target = card?.classList.contains("card") ? card : null;
  state.popoverItemId = target?.dataset.id || null;
  document.querySelectorAll(".card.action-popover-anchor").forEach(candidate => candidate.classList.toggle("action-popover-anchor", candidate === target));
}

function targetedItemForShortcut() {
  if (selectedCount() > 0) return null;
  const targetId = state.popoverItemId || state.activeTileId;
  return targetId ? state.catalog?.items?.find(item => item.id === targetId) || null : null;
}

function cardMarkup(item, index) {
  const selected = isSelected(item);
  const thumb = `<img class="poster" src="${escapeHtml(item.thumbnail_url)}" alt="Thumbnail for ${escapeHtml(item.name)}" loading="lazy">`;
  const play = item.kind === "video" ? `<button class="play-here" type="button" aria-label="Play ${escapeHtml(item.name)} here" title="Play here"></button>` : "";
  const viewer = viewerUrl(item);
  const folder = String(item.folder || state.catalog.source_label || "");
  return `<article class="card ${selected ? "selected" : ""}" data-id="${escapeHtml(item.id)}" style="animation-delay:${Math.min(index, 12) * 18}ms">
    <div class="preview"><a class="preview-link viewer-link" href="${escapeHtml(viewer)}" target="_blank" rel="noopener" aria-label="Open ${escapeHtml(item.name)} in a new tab">${thumb}</a>${play}<label class="card-select" title="Select ${escapeHtml(item.name)}"><input class="card-checkbox" type="checkbox" ${selected ? "checked" : ""} aria-label="Select ${escapeHtml(item.name)}"></label><button class="tile-actions-trigger" type="button" aria-haspopup="menu" aria-controls="item-action-popover" aria-expanded="false" aria-label="Show destination actions for ${escapeHtml(item.name)}" title="Show destination actions"><span aria-hidden="true">…</span></button></div>
    <div class="card-body"><div class="card-heading"><h2 class="name" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</h2><div class="metadata"><span>${escapeHtml(item.size_label)}</span><span>${escapeHtml(item.modified_label)}</span></div></div><p class="folder" title="${escapeHtml(folder)}">${iconMarkup("folder")}${escapeHtml(folder)}</p><div class="card-utility-actions"><a class="item-action viewer-link" href="${escapeHtml(viewer)}" target="_blank" rel="noopener" title="Open in a new tab · ⇧O with one item selected">↗ Open <kbd class="item-shortcut">⇧O</kbd></a><button class="item-action reveal" type="button" title="Reveal in Finder · ⇧F with one item selected">Finder <kbd class="item-shortcut">⇧F</kbd></button></div></div></article>`;
}

function stopActivePlayer() {
  if (!state.active) return;
  state.active.video.pause();
  if (state.active.card.isConnected) state.active.card.querySelector(".preview").innerHTML = state.active.original;
  state.active = null;
}

function render() {
  if (!state.catalog) return;
  closeItemActionPopover();
  stopActivePlayer();
  const items = state.catalog.items;
  let emptyMessage = "No media matches this view.";
  if (state.catalog.total === 0 && !state.query && state.kind === "both") {
    emptyMessage = `<section class="empty-onboarding"><p class="eyebrow">New collection</p><h2>Nothing to sort here yet</h2><p>Choose a folder with pictures or videos, or start with your Desktop. This empty collection remains available if you need it.</p><div class="empty-actions"><button class="button primary empty-choose" type="button">Choose a folder…</button><button class="button empty-desktop" type="button">Use Desktop</button></div><small>Each folder keeps its own local SlideSorter state and destinations.</small></section>`;
  }
  if (state.kind === "picture" && state.catalog.media_mode === "videos") emptyMessage = `Pictures are not in the current catalog. <button class="button empty-settings" type="button">Change Settings</button>`;
  if (state.kind === "video" && state.catalog.media_mode === "pictures") emptyMessage = `Videos are not in the current catalog. <button class="button empty-settings" type="button">Change Settings</button>`;
  gallery.innerHTML = items.length ? items.map(cardMarkup).join("") : `<div class="empty">${emptyMessage}</div>`;
  applyCardTints();
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

async function copyText(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const helper = document.createElement("textarea");
  helper.value = value;
  helper.setAttribute("readonly", "");
  helper.style.position = "fixed";
  helper.style.opacity = "0";
  document.body.append(helper);
  helper.select();
  const copied = document.execCommand("copy");
  helper.remove();
  if (!copied) throw new Error("Could not copy the update command");
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
    state.collectionRoot = result.media_root || state.collectionRoot;
    if (result.media_root && state.thumbnailRoot !== result.media_root) {
      state.thumbnailRoot = result.media_root;
      restoreThumbnailSize(result.media_root);
    }
    restoreSelectionForCatalog();
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

async function performBulkMove(action) {
  closeActionMenus();
  closeItemActionPopover();
  setActiveTile(null);
  const count = selectedCount();
  if (!count || state.bulkMoving) return;
  state.bulkMoving = true;
  const buttons = [...document.querySelectorAll(".move-action")];
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
    state.bulkMoving = false;
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
  const wasOpen = sheet.classList.contains("open");
  sheet.classList.remove("open");
  sheet.setAttribute("aria-hidden", "true");
  scrim.hidden = true;
  if (wasOpen) document.querySelector("#settings-open").focus();
}

function newActionId() {
  return `action-${crypto.randomUUID().replaceAll("-", "")}`;
}

function destinationRowMarkup(action, actions = []) {
  const presentation = action.display_label ? action : actionPresentation(action.label);
  const shortcut = normalizedShortcut(action.shortcut) || suggestedShortcutForAction(action, actions);
  return `<article class="destination-row" data-action-id="${escapeHtml(action.id || newActionId())}" data-root-mode="${escapeHtml(action.root_mode || "custom")}">
    <div class="destination-row-head"><span class="destination-order"></span><span class="destination-preview tone-${escapeHtml(presentation.tone)}">${iconMarkup(presentation.icon)}<strong>${escapeHtml(presentation.display_label)}</strong></span><div class="destination-order-actions"><button class="mini-button destination-up" type="button" aria-label="Move destination up">↑</button><button class="mini-button destination-down" type="button" aria-label="Move destination down">↓</button><button class="mini-button destination-delete" type="button" aria-label="Remove destination">×</button></div></div>
    <label class="compact-field"><span>Button label</span><input class="destination-label" value="${escapeHtml(action.label || "")}" maxlength="120" placeholder="Review later (blue clock icon)" required></label>
    <label class="compact-field destination-shortcut-field"><span>Shortcut key</span><input class="destination-shortcut" value="${escapeHtml(shortcut)}" maxlength="1" inputmode="text" autocomplete="off" spellcheck="false" placeholder="None" title="One letter or number; leave blank for no shortcut"></label>
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
  destinationList.innerHTML = actions.map(action => destinationRowMarkup(action, actions)).join("");
  refreshDestinationRows();
}

function configuredDestinations(config) {
  if (Array.isArray(config.actions) && config.actions.length) return config.actions;
  const mediaRoot = String(config.media_root || "").replace(/\/+$/, "");
  return [
    {
      id: "stage",
      label: "Stage",
      root: config.staged_root || `${mediaRoot}/Staged`,
      shortcut: "",
    },
    {
      id: "remove",
      label: "Remove (use a red trash can glyph)",
      root: config.removed_root || `${mediaRoot}/Removed`,
      shortcut: "",
    },
  ];
}

function collectDestinationActions() {
  return [...destinationList.querySelectorAll(".destination-row")].map(row => ({
    id: row.dataset.actionId,
    label: row.querySelector(".destination-label").value.trim(),
    root: row.querySelector(".destination-root").value.trim(),
    shortcut: row.querySelector(".destination-shortcut").value.trim(),
  }));
}

function suggestedDestinationLabel() {
  const existing = new Set([...destinationList.querySelectorAll(".destination-label")].map(input => actionPresentation(input.value).display_label.toLocaleLowerCase()));
  let number = 1;
  let candidate = "New label";
  while (existing.has(candidate.toLocaleLowerCase())) {
    number += 1;
    candidate = `New label ${number}`;
  }
  return candidate;
}

function normalizedRoot(value) {
  const root = String(value || "").trim();
  return root === "/" ? root : root.replace(/\/+$/, "");
}

function proposedDestinationName(action) {
  const display = actionPresentation(action.label).display_label;
  return display.replaceAll("/", "-").replaceAll("\\", "-").replace(/^[. ]+|[. ]+$/g, "") || action.id;
}

function proposedDestinationPath(root, action) {
  const selectedRoot = normalizedRoot(root);
  if (!selectedRoot) return "";
  const name = proposedDestinationName(action);
  return selectedRoot === "/" ? `/${name}` : `${selectedRoot}/${name}`;
}

function updateProposedDestinationRoots(root) {
  const selectedRoot = normalizedRoot(root);
  const currentRoot = normalizedRoot(state.collectionRoot);
  const useCurrentRoots = Boolean(selectedRoot && currentRoot && selectedRoot === currentRoot);
  const savedById = new Map(state.collectionActions.map(action => [action.id, action]));
  document.querySelectorAll(".destination-row").forEach(row => {
    const action = savedById.get(row.dataset.actionId);
    const input = row.querySelector(".destination-root");
    if (useCurrentRoots && action) input.value = action.root;
    else if (selectedRoot) {
      const label = row.querySelector(".destination-label").value;
      input.value = proposedDestinationPath(selectedRoot, { id: row.dataset.actionId, label });
    }
  });
  document.querySelector("#destination-root-note").hidden = !selectedRoot || useCurrentRoots;
}

function hideCollectionCreate() {
  state.collectionPending = null;
  document.querySelector("#collection-create").hidden = true;
}

function renderRecentCollections(payload) {
  const collections = payload?.collections || [];
  const region = document.querySelector("#recent-collections");
  const list = document.querySelector("#recent-collection-list");
  list.innerHTML = collections.map(collection => {
    const root = String(collection.root || "");
    const name = root.split("/").filter(Boolean).pop() || root;
    return `<button class="recent-collection ${collection.active ? "active" : ""}" type="button" data-root="${escapeHtml(root)}" title="${escapeHtml(root)}">${escapeHtml(name)}</button>`;
  }).join("");
  region.hidden = collections.length < 2;
}

async function loadRecentCollections(payload = null) {
  try { renderRecentCollections(payload || await jsonRequest("/api/collections")); }
  catch { /* The gallery remains usable if a recent-collection index is unavailable. */ }
}

async function activateCollection(root, copyLabels = true) {
  const controls = [...document.querySelectorAll("#media-root, [data-choose='media_root'], .recent-collection")];
  controls.forEach(control => { control.disabled = true; });
  try {
    const result = await jsonRequest("/api/switch-collection", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ media_root: root, copy_labels: copyLabels }),
    });
    clearSelection();
    state.collectionRoot = result.settings?.media_root || root;
    state.collectionActions = configuredDestinations(result.settings || {});
    state.page = 1;
    state.query = "";
    search.value = "";
    state.kind = "both";
    document.querySelectorAll(".kind-option").forEach(option => option.classList.toggle("active", option.dataset.kind === "both"));
    hideCollectionCreate();
    document.querySelector("#media-root").value = state.collectionRoot;
    closeSettings();
    await loadCatalog();
    await updateUndoState();
    await loadRecentCollections(result.collections);
    const createdRoots = Array.isArray(result.created_destination_roots) ? result.created_destination_roots : [];
    toast(result.created ? `New collection created${createdRoots.length ? " · destinations ready" : ""}` : "Collection opened");
  } catch (error) { toast(error.message, { error: true, duration: 12000 }); }
  finally { controls.forEach(control => { control.disabled = false; }); }
}

async function prepareCollectionSwitch(root) {
  const target = String(root || "").trim();
  if (!target) { toast("Choose a root tree first", { error: true }); return; }
  try {
    const status = await jsonRequest("/api/collection-status", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ media_root: target }),
    });
    document.querySelector("#media-root").value = status.root;
    updateProposedDestinationRoots(status.root);
    if (status.same_collection) { hideCollectionCreate(); toast("This collection is already open"); return; }
    if (status.status === "existing") { await activateCollection(status.root, false); return; }
    state.collectionPending = status.root;
    document.querySelector("#collection-create-root").textContent = status.root;
    document.querySelector("#collection-create").hidden = false;
    document.querySelector("#collection-create-confirm").focus();
  } catch (error) { toast(error.message, { error: true, duration: 12000 }); }
}

async function useDesktopCollection() {
  await openSettings();
  const root = document.querySelector("#media-root");
  root.value = "~/Desktop";
  updateProposedDestinationRoots(root.value);
  await prepareCollectionSwitch(root.value);
}

async function openSettings() {
  try {
    const config = await jsonRequest("/api/settings");
    document.querySelector("#media-root").value = config.media_root;
    state.collectionRoot = config.media_root;
    state.collectionActions = configuredDestinations(config);
    hideCollectionCreate();
    renderDestinationEditor(state.collectionActions);
    updateProposedDestinationRoots(config.media_root);
    document.querySelector("#keep-structure").checked = config.keep_structure !== false;
    state.appearance = config.appearance || "system";
    document.querySelector("#appearance").value = state.appearance;
    document.querySelector("#media-mode").value = config.media_mode;
    document.querySelector("#gallery-title").value = config.title;
    document.querySelector("#source-label").value = config.source_label;
    document.querySelector("#page-capacity").value = String(state.pageSize);
    document.querySelector("#history-retention-days").value = String(config.history_retention_days ?? 90);
    scrim.hidden = false;
    sheet.classList.add("open");
    sheet.setAttribute("aria-hidden", "false");
    await loadRecentCollections();
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
    if (button.dataset.choose === "media_root") {
      hideCollectionCreate();
      updateProposedDestinationRoots(result.path);
      await prepareCollectionSwitch(result.path);
    }
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

function actionForShortcut(key) {
  const candidate = String(key || "").toLocaleLowerCase();
  if (reservedShortcuts.has(candidate)) return null;
  const matches = (state.catalog?.actions || []).filter(action => shortcutForAction(action) === candidate);
  return matches.length === 1 ? matches[0] : null;
}

function closeActionMenus(except = null) {
  document.querySelectorAll(".action-menu-wrap.open").forEach(wrapper => {
    if (wrapper === except) return;
    wrapper.classList.remove("open");
    wrapper.closest(".card")?.classList.remove("action-menu-open");
    wrapper.querySelector(".action-menu").hidden = true;
    wrapper.querySelector(".more-actions").setAttribute("aria-expanded", "false");
  });
}

let itemActionTrigger = null;

function closeItemActionPopover({ restoreFocus = false } = {}) {
  const trigger = itemActionTrigger;
  if (trigger) trigger.setAttribute("aria-expanded", "false");
  itemActionTrigger = null;
  itemActionPopover.hidden = true;
  itemActionPopover.replaceChildren();
  itemActionPopover.style.removeProperty("left");
  itemActionPopover.style.removeProperty("top");
  setPopoverTarget(null);
  if (restoreFocus && trigger?.isConnected) trigger.focus();
}

function positionItemActionPopover(trigger) {
  const margin = 12;
  const gap = 8;
  const triggerRect = trigger.getBoundingClientRect();
  const popoverRect = itemActionPopover.getBoundingClientRect();
  const maximumLeft = Math.max(margin, window.innerWidth - popoverRect.width - margin);
  const left = Math.min(maximumLeft, Math.max(margin, triggerRect.right - popoverRect.width));
  const below = triggerRect.bottom + gap;
  const above = triggerRect.top - popoverRect.height - gap;
  const top = below + popoverRect.height <= window.innerHeight - margin
    ? below
    : Math.max(margin, above);
  itemActionPopover.style.left = `${Math.round(left)}px`;
  itemActionPopover.style.top = `${Math.round(top)}px`;
}

function openItemActionPopover(trigger, item, focusFirstAction = false) {
  const actions = state.catalog?.actions || [];
  if (!actions.length) return;
  closeActionMenus();
  closeItemActionPopover();
  itemActionTrigger = trigger;
  trigger.setAttribute("aria-expanded", "true");
  setPopoverTarget(trigger.closest(".card"));
  itemActionPopover.innerHTML = `<header class="item-action-popover-head"><span>Move this item</span><strong title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</strong></header><div class="item-action-popover-actions">${actions.map(action => actionButtonMarkup(action, "item-popover-action", true, `Move only ${item.name} to ${action.display_label}`)).join("")}</div>`;
  itemActionPopover.querySelectorAll(".move-action").forEach(button => button.setAttribute("role", "menuitem"));
  itemActionPopover.hidden = false;
  positionItemActionPopover(trigger);
  if (focusFirstAction) itemActionPopover.querySelector(".move-action")?.focus();
}

function toggleItemActionPopover(trigger, item, focusFirstAction = false) {
  if (itemActionTrigger === trigger && !itemActionPopover.hidden) {
    closeItemActionPopover({ restoreFocus: focusFirstAction });
    return;
  }
  openItemActionPopover(trigger, item, focusFirstAction);
}

function toggleActionMenu(button) {
  const wrapper = button.closest(".action-menu-wrap");
  const opening = !wrapper.classList.contains("open");
  closeActionMenus(wrapper);
  wrapper.classList.toggle("open", opening);
  wrapper.closest(".card")?.classList.toggle("action-menu-open", opening);
  wrapper.querySelector(".action-menu").hidden = !opening;
  button.setAttribute("aria-expanded", String(opening));
}

gallery.addEventListener("click", event => {
  if (event.target.closest(".empty-settings")) { openSettings(); return; }
  if (event.target.closest(".empty-choose")) { openSettings(); return; }
  if (event.target.closest(".empty-desktop")) { useDesktopCollection(); return; }
  const card = event.target.closest(".card");
  if (!card || !state.catalog) return;
  const item = state.catalog.items.find(candidate => candidate.id === card.dataset.id);
  if (!item) return;
  const trigger = event.target.closest(".tile-actions-trigger");
  if (trigger) {
    event.preventDefault();
    event.stopPropagation();
    toggleItemActionPopover(trigger, item, event.detail === 0);
    return;
  }
  if (event.target.closest(".card-select")) {
    if (!event.target.matches(".card-checkbox")) event.preventDefault();
    handleCardSelection(item, event, true);
    return;
  }
  if (event.target.closest(".play-here")) { playHere(card, item); return; }
  if (event.target.closest(".reveal")) { jsonRequest("/api/reveal", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: item.id }) }).catch(error => toast(error.message, { error: true })); return; }
  if (event.target.closest("a")) {
    if (event.metaKey || event.ctrlKey || event.shiftKey) {
      event.preventDefault();
      handleCardSelection(item, event);
    }
    return;
  }
  handleCardSelection(item, event);
});

itemActionPopover.addEventListener("click", event => {
  const move = event.target.closest(".move-action");
  if (!move) return;
  const action = configuredAction(move.dataset.actionId);
  const item = state.catalog?.items?.find(candidate => candidate.id === state.popoverItemId);
  if (!action || !item) return;
  state.selectionAll = false;
  state.allCriteria = null;
  state.selectedIds.clear();
  state.excludedIds.clear();
  setItemSelected(item, true);
  state.lastSelectedId = item.id;
  closeItemActionPopover();
  updateSelectionUI();
  performBulkMove(action);
});

itemActionPopover.addEventListener("keydown", event => {
  if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
  const actions = [...itemActionPopover.querySelectorAll(".move-action:not(:disabled)")];
  if (!actions.length) return;
  event.preventDefault();
  const current = Math.max(0, actions.indexOf(document.activeElement));
  const next = event.key === "Home" ? 0
    : event.key === "End" ? actions.length - 1
      : event.key === "ArrowDown" ? (current + 1) % actions.length
        : (current - 1 + actions.length) % actions.length;
  actions[next].focus();
});

function updateActiveTileFromPointer(event) {
  if (event.pointerType === "touch") return;
  setActiveTile(event.target.closest?.(".card") || null);
}

// Active-tile tracking remains intentionally separate from rendering. It only
// gives a destination shortcut an unambiguous current item; it never reveals
// or positions controls.
gallery.addEventListener("pointerover", updateActiveTileFromPointer, { passive: true });
gallery.addEventListener("pointermove", updateActiveTileFromPointer, { passive: true });
gallery.addEventListener("pointerout", event => {
  if (event.relatedTarget?.closest?.("#gallery")) return;
  setActiveTile(null);
}, { passive: true });

let searchTimer;
search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { state.query = search.value; state.page = 1; state.lastSelectedId = null; loadCatalog(); }, 250);
});
sort.addEventListener("change", () => { state.sort = sort.value; state.page = 1; loadCatalog(); });
thumbnailSize.addEventListener("input", event => {
  closeItemActionPopover();
  setActiveTile(null);
  animateThumbnailSize(event.currentTarget.value);
});
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
window.addEventListener("wheel", event => {
  if (event.deltaY < 0 && window.scrollY <= 1 && document.body.classList.contains("selection-active")) {
    document.body.classList.add("selection-top-revealed");
  }
}, { passive: true });
bulkBar.addEventListener("click", event => {
  const more = event.target.closest(".more-actions");
  if (more) { toggleActionMenu(more); return; }
  const move = event.target.closest(".move-action");
  if (!move) return;
  const action = configuredAction(move.dataset.actionId);
  if (action) performBulkMove(action);
});
window.addEventListener("resize", () => {
  closeItemActionPopover();
  setActiveTile(null);
  if (!bulkBar.hidden && state.catalog) renderBulkActions(state.catalog.actions || []);
});
window.addEventListener("scroll", () => {
  closeItemActionPopover();
  setActiveTile(null);
}, { passive: true });
window.addEventListener("blur", () => {
  closeItemActionPopover();
  setActiveTile(null);
});
document.querySelector("#refresh").addEventListener("click", refreshCatalog);
undoLast.addEventListener("click", () => undo());
document.querySelector("#history-link").addEventListener("click", () => {
  const visiblePageSize = Number(pageSize.value);
  sessionStorage.setItem(galleryReturnKey, JSON.stringify({
    page: state.page,
    pageSize: visiblePageSize >= 25 && visiblePageSize <= 500 && visiblePageSize % 25 === 0 ? visiblePageSize : state.pageSize,
    query: search.value,
    kind: state.kind,
    sort: state.sort,
    scrollY: window.scrollY,
  }));
});
document.querySelector("#settings-open").addEventListener("click", openSettings);
document.querySelector("#media-root").addEventListener("input", event => {
  hideCollectionCreate();
  updateProposedDestinationRoots(event.currentTarget.value);
});
document.querySelector("#media-root").addEventListener("change", event => {
  if (String(event.currentTarget.value).trim()) prepareCollectionSwitch(event.currentTarget.value);
});
document.querySelector("#collection-create-cancel").addEventListener("click", hideCollectionCreate);
document.querySelector("#collection-create-confirm").addEventListener("click", () => {
  if (state.collectionPending) activateCollection(state.collectionPending, document.querySelector("#collection-copy-labels").checked);
});
document.querySelector("#recent-collection-list").addEventListener("click", event => {
  const button = event.target.closest(".recent-collection");
  if (button) {
    document.querySelector("#media-root").value = button.dataset.root;
    updateProposedDestinationRoots(button.dataset.root);
    prepareCollectionSwitch(button.dataset.root);
  }
});
document.querySelector("#appearance").addEventListener("change", async event => {
  const select = event.currentTarget;
  const previous = state.appearance;
  const appearance = select.value;
  window.SlideSorterAppearance?.apply(appearance);
  select.disabled = true;
  try {
    const config = await jsonRequest("/api/appearance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ appearance }),
    });
    state.appearance = config.appearance;
    select.value = state.appearance;
    window.SlideSorterAppearance?.apply(state.appearance);
    toast(`Appearance: ${state.appearance === "system" ? "System default" : state.appearance[0].toUpperCase() + state.appearance.slice(1)}`);
  } catch (error) {
    state.appearance = previous;
    select.value = previous;
    window.SlideSorterAppearance?.apply(previous);
    toast(error.message, { error: true });
  } finally { select.disabled = false; }
});
document.querySelector("#settings-close").addEventListener("click", closeSettings);
document.querySelector("#settings-cancel").addEventListener("click", closeSettings);
scrim.addEventListener("click", closeSettings);
document.querySelector("#update-check").addEventListener("click", async event => {
  const button = event.currentTarget;
  const status = document.querySelector("#update-status");
  const copy = document.querySelector("#update-copy");
  button.disabled = true;
  button.textContent = "Checking GitHub…";
  copy.hidden = true;
  status.classList.remove("error", "available");
  status.textContent = "Contacting GitHub’s public release service…";
  try {
    const update = await jsonRequest("/api/update-check", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    if (update.update_available) {
      status.classList.add("available");
      status.textContent = `Version ${update.latest_version} is available. Open Release notes to review it, then update with Homebrew if that is how you installed SlideSorter.`;
      copy.hidden = false;
    } else {
      status.textContent = `You’re up to date with SlideSorter ${update.current_version}. This manual check contacted GitHub only; no collection data was sent.`;
    }
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = "Check for updates";
  }
});
document.querySelector("#update-copy").addEventListener("click", async event => {
  try {
    await copyText("brew update && brew upgrade slidesorter");
    event.currentTarget.textContent = "Copied";
    setTimeout(() => { event.currentTarget.textContent = "Copy Homebrew update"; }, 1800);
  } catch (error) { toast(error.message, { error: true }); }
});
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
  const row = event.target.closest(".destination-row");
  if (event.target.matches(".destination-label")) {
    refreshDestinationRows();
    if (row?.dataset.rootMode === "suggested") {
      row.querySelector(".destination-root").value = proposedDestinationPath(document.querySelector("#media-root").value, {
        id: row.dataset.actionId, label: event.target.value,
      });
    }
  }
  if (event.target.matches(".destination-root") && row) row.dataset.rootMode = "custom";
  if (event.target.matches(".destination-shortcut")) {
    event.target.value = [...event.target.value.trim()].slice(0, 1).join("");
  }
});
document.querySelector("#destination-add").addEventListener("click", () => {
  const id = newActionId();
  const label = suggestedDestinationLabel();
  const existing = collectDestinationActions();
  const shortcut = suggestedShortcutForAction({ label }, existing);
  destinationList.insertAdjacentHTML("beforeend", destinationRowMarkup({
    id, label, shortcut, root: proposedDestinationPath(document.querySelector("#media-root").value, { id, label }), root_mode: "suggested",
  }, [...existing, { label, shortcut }]));
  refreshDestinationRows();
  destinationList.querySelector(".destination-row:last-child .destination-label").focus();
});
document.querySelector("#history-rebuild").addEventListener("click", async event => {
  const button = event.currentTarget;
  const retention = Number.parseInt(document.querySelector("#history-retention-days").value, 10);
  if (!Number.isInteger(retention) || retention < 0 || retention > 3650) {
    toast("History retention must be between 0 and 3650 days", { error: true });
    return;
  }
  button.disabled = true;
  button.textContent = "Checking…";
  try {
    const result = await jsonRequest("/api/rebuild-history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ retention_days: retention }),
    });
    const details = [
      `${Number(result.available || 0).toLocaleString()} available`,
      `${Number(result.purged || 0).toLocaleString()} marked Purged`,
    ];
    if (result.restored) details.push(`${Number(result.restored).toLocaleString()} already restored`);
    if (result.conflicts) details.push(`${Number(result.conflicts).toLocaleString()} conflicts`);
    if (result.expired) details.push(`${Number(result.expired).toLocaleString()} expired records removed`);
    toast(`History rebuilt · ${details.join(" · ")}`, { duration: 10000 });
    await updateUndoState();
  } catch (error) { toast(error.message, { error: true, duration: 12000 }); }
  finally { button.disabled = false; button.textContent = "Rebuild History"; }
});
document.querySelector("#settings-form").addEventListener("submit", async event => {
  event.preventDefault();
  const save = document.querySelector("#settings-save");
  save.disabled = true;
  save.textContent = "Rebuilding…";
  try {
    const form = new FormData(event.currentTarget);
    const settings = Object.fromEntries(form);
    if (settings.media_root !== state.collectionRoot) {
      throw new Error("Use Switch collection to open a different root tree. This collection’s state stays with its current root.");
    }
    settings.actions = collectDestinationActions();
    settings.keep_structure = document.querySelector("#keep-structure").checked;
    const requestedPageSize = Math.max(25, Math.min(500, Math.round(Number(settings.page_capacity || 100) / 25) * 25));
    delete settings.page_capacity;
    const config = await jsonRequest("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(settings) });
    state.collectionActions = configuredDestinations(config);
    state.appearance = config.appearance || "system";
    window.SlideSorterAppearance?.apply(state.appearance);
    state.pageSize = requestedPageSize;
    pageSize.value = String(requestedPageSize);
    localStorage.setItem("media-gallery-page-size", String(requestedPageSize));
    closeSettings();
    state.kind = "both";
    state.page = 1;
    document.querySelectorAll(".kind-option").forEach(option => option.classList.toggle("active", option.dataset.kind === "both"));
    await loadCatalog();
    await updateUndoState();
    const created = Array.isArray(config.created_destination_roots) ? config.created_destination_roots : [];
    toast(created.length ? `Settings saved · created ${created.length === 1 ? "destination folder" : `${created.length} destination folders`}` : "Settings saved and catalog rebuilt");
  } catch (error) { toast(error.message, { error: true, duration: 12000 }); }
  finally { save.disabled = false; save.textContent = "Save & rebuild"; }
});

document.addEventListener("keydown", event => {
  if (event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey && !event.target.matches("input,textarea,select")) { event.preventDefault(); search.focus(); }
  if (event.key === "Escape" && sheet.classList.contains("open")) closeSettings();
  if (event.key === "Escape") {
    closeActionMenus();
    closeItemActionPopover({ restoreFocus: true });
  }
  if (event.key === "Escape" && state.active) {
    event.preventDefault();
    stopActivePlayer();
    updateSelectionUI();
    return;
  }
  if (event.code === "Space" && state.active && !event.target.matches("input,textarea,button,a,select")) { event.preventDefault(); state.active.video.paused ? state.active.video.play() : state.active.video.pause(); }
  const typingTarget = event.target.matches("input,textarea,select,[contenteditable]");
  const selectionShortcutTarget = event.target.matches(".card-checkbox") || !typingTarget;
  if (!event.metaKey && !event.ctrlKey && !event.altKey && !sheet.classList.contains("open") && !state.active && selectionShortcutTarget) {
    if (!event.shiftKey && event.code === "KeyU") {
      if (!undoLast.disabled) {
        event.preventDefault();
        undo();
      }
      return;
    }
    if (event.shiftKey && selectedCount() === 1) {
      if (event.code === "KeyO") { event.preventDefault(); openSingleSelectedItem(); return; }
      if (event.code === "KeyF") { event.preventDefault(); revealSingleSelectedItem(); return; }
    }
  }
  if (
    event.key.length === 1 && !event.shiftKey && !event.metaKey && !event.ctrlKey && !event.altKey && !event.repeat
    && !sheet.classList.contains("open") && !state.active && !typingTarget
  ) {
    const action = actionForShortcut(event.key);
    if (action) {
      const targetedItem = targetedItemForShortcut();
      if (selectedCount() === 0 && !targetedItem) return;
      event.preventDefault();
      if (targetedItem) {
        setItemSelected(targetedItem, true);
        state.lastSelectedId = targetedItem.id;
        updateSelectionUI();
      }
      toast(`${action.display_label} (${shortcutForAction(action).toUpperCase()})`);
      performBulkMove(action);
    }
  }
});

document.addEventListener("click", event => {
  if (!event.target.closest(".action-menu-wrap")) closeActionMenus();
  if (!event.target.closest(".tile-actions-trigger, .item-action-popover")) closeItemActionPopover();
});

document.addEventListener("pointerdown", event => {
  if (!event.target.closest?.("#gallery, .item-action-popover")) setActiveTile(null);
}, true);

gallery.addEventListener("focusin", event => {
  const card = event.target.closest(".card");
  if (card) setActiveTile(card);
});

gallery.addEventListener("focusout", event => {
  const card = event.target.closest(".card");
  if (!card) return;
  requestAnimationFrame(() => {
    if (card.contains(document.activeElement)) return;
    if (state.activeTileId === card.dataset.id) setActiveTile(null);
  });
});

Promise.all([loadCatalog(), updateUndoState()]).then(() => {
  if (!restoredView) return;
  restoreScrollPosition(restoredView.scrollY);
  sessionStorage.removeItem(galleryReturnKey);
  restoredView = null;
});

window.addEventListener("pageshow", event => {
  if (!event.persisted) return;
  try {
    const returnView = JSON.parse(sessionStorage.getItem(galleryReturnKey) || "null");
    if (returnView) restoreScrollPosition(returnView.scrollY);
  } catch { /* Ignore an invalid session fallback and keep the browser-restored view. */ }
  sessionStorage.removeItem(galleryRestoreKey);
  sessionStorage.removeItem(galleryReturnKey);
});
