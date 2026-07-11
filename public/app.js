'use strict';

// ---- state ----
const state = {
  images: [],
  total: 0,
  filters: { q: '', tag: null, minRating: 0, rejected: false, sort: 'newest' },
  selected: -1,
  lightbox: -1, // index into state.images, -1 = closed
  loading: false,
};
const PAGE = 200;
const GRID_ROW_HEIGHT = 220;

const $ = (sel) => document.querySelector(sel);
const grid = $('#grid');

// ---- api ----
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'content-type': 'application/json' },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ---- grid ----
function buildQuery(offset) {
  const f = state.filters;
  const p = new URLSearchParams({ offset, limit: PAGE, sort: f.sort });
  if (f.q) p.set('q', f.q);
  if (f.tag) p.set('tag', f.tag);
  if (f.minRating) p.set('minRating', f.minRating);
  if (f.rejected) p.set('rejected', '1');
  return p.toString();
}

async function loadImages(reset = false) {
  if (state.loading) return;
  state.loading = true;
  try {
    const offset = reset ? 0 : state.images.length;
    const data = await api(`/api/images?${buildQuery(offset)}`);
    state.total = data.total;
    if (reset) {
      state.images = data.images;
      state.selected = data.images.length ? 0 : -1;
      grid.innerHTML = '';
    } else {
      state.images.push(...data.images);
    }
    for (let i = offset; i < state.images.length; i++) grid.appendChild(makeCard(i));
    ensureSentinel();
    updateSelection();
    $('#count').textContent = `${state.total} 枚`;
  } finally {
    state.loading = false;
  }
}

function makeCard(index) {
  const img = state.images[index];
  const ar = img.width && img.height ? img.width / img.height : 1;
  const card = document.createElement('div');
  card.className = 'card';
  card.dataset.index = index;
  card.style.flexBasis = `${Math.round(ar * GRID_ROW_HEIGHT)}px`;
  card.style.flexGrow = ar;
  card.style.backgroundColor = img.color ?? '#222';
  if (img.rejected) card.classList.add('rejected');

  const el = document.createElement('img');
  el.loading = 'lazy';
  el.src = `/thumbs/${img.id}.webp`;
  el.alt = img.filename;
  card.appendChild(el);

  const rating = document.createElement('span');
  rating.className = 'badge-rating';
  card.appendChild(rating);
  const reject = document.createElement('span');
  reject.className = 'badge-reject';
  reject.textContent = '🗑';
  card.appendChild(reject);
  syncCardBadges(card, img);

  card.addEventListener('click', () => setSelected(index));
  card.addEventListener('dblclick', () => openLightbox(index));
  return card;
}

function syncCardBadges(card, img) {
  card.querySelector('.badge-rating').textContent = img.rating > 0 ? '★'.repeat(img.rating) : '';
  card.querySelector('.badge-rating').style.display = img.rating > 0 ? '' : 'none';
  card.classList.toggle('rejected', !!img.rejected);
}

function cardAt(index) {
  return grid.querySelector(`.card[data-index="${index}"]`);
}

function setSelected(index) {
  if (index < 0 || index >= state.images.length) return;
  state.selected = index;
  updateSelection();
  if (state.lightbox >= 0) renderLightbox(index);
}

function updateSelection() {
  grid.querySelectorAll('.card.selected').forEach((c) => c.classList.remove('selected'));
  const card = cardAt(state.selected);
  if (card) {
    card.classList.add('selected');
    card.scrollIntoView({ block: 'nearest' });
  }
}

// Move selection up/down by finding the geometrically nearest card
// in the adjacent row (justified layout has variable columns per row).
function moveVertical(dir) {
  const cur = cardAt(state.selected);
  if (!cur) return;
  const curRect = cur.getBoundingClientRect();
  const curCenter = curRect.left + curRect.width / 2;
  let best = null;
  let bestDist = Infinity;
  for (const card of grid.querySelectorAll('.card')) {
    const r = card.getBoundingClientRect();
    const sameRow = Math.abs(r.top - curRect.top) < 4;
    if (sameRow) continue;
    if (dir > 0 ? r.top <= curRect.top : r.top >= curRect.top) continue;
    const rowDist = Math.abs(r.top - curRect.top);
    const xDist = Math.abs(r.left + r.width / 2 - curCenter);
    const score = rowDist * 10000 + xDist;
    if (score < bestDist) {
      bestDist = score;
      best = card;
    }
  }
  if (best) setSelected(Number(best.dataset.index));
}

// infinite scroll
let sentinel = null;
function ensureSentinel() {
  sentinel?.remove();
  if (state.images.length >= state.total) return;
  sentinel = document.createElement('div');
  sentinel.style.cssText = 'flex-basis:100%;height:1px';
  grid.appendChild(sentinel);
  observer.observe(sentinel);
}
const observer = new IntersectionObserver((entries) => {
  if (entries.some((e) => e.isIntersecting)) loadImages(false);
});

// ---- rating / reject actions ----
async function rate(index, rating) {
  const img = state.images[index];
  if (!img) return;
  img.rating = rating;
  await api(`/api/images/${img.id}`, { method: 'PATCH', body: { rating } });
  const card = cardAt(index);
  if (card) syncCardBadges(card, img);
  if (state.lightbox === index) renderStars($('#lb-stars'), img.rating, (v) => rate(index, v));
}

async function toggleReject(index) {
  const img = state.images[index];
  if (!img) return;
  img.rejected = img.rejected ? 0 : 1;
  await api(`/api/images/${img.id}`, { method: 'PATCH', body: { rejected: !!img.rejected } });
  const card = cardAt(index);
  if (card) syncCardBadges(card, img);
}

function renderStars(container, value, onChange, clearable = false) {
  container.innerHTML = '';
  for (let i = 1; i <= 5; i++) {
    const s = document.createElement('span');
    s.className = 'star' + (i <= value ? ' on' : '');
    s.textContent = i <= value ? '★' : '☆';
    s.addEventListener('click', () => onChange(clearable && i === value ? 0 : i));
    container.appendChild(s);
  }
}

// ---- lightbox ----
function openLightbox(index) {
  state.lightbox = index;
  $('#lightbox').hidden = false;
  renderLightbox(index);
}

function closeLightbox() {
  state.lightbox = -1;
  $('#lightbox').hidden = true;
  $('#lb-image').src = '';
}

function renderLightbox(index) {
  state.lightbox = index;
  const img = state.images[index];
  if (!img) return closeLightbox();
  $('#lb-image').src = `/files/${img.id}`;
  $('#lb-name').textContent = img.filename;
  const kb = (img.size / 1024).toFixed(0);
  const date = new Date(img.mtime).toLocaleDateString();
  $('#lb-meta').textContent = `${img.width}×${img.height} · ${kb} KB · ${date}`;
  renderStars($('#lb-stars'), img.rating, (v) => rate(index, v));
  renderLbTags(img);
}

function renderLbTags(img) {
  const box = $('#lb-tags');
  box.innerHTML = '';
  for (const tag of img.tags) {
    const pill = document.createElement('span');
    pill.className = 'tag';
    pill.textContent = tag;
    const x = document.createElement('span');
    x.className = 'tag-x';
    x.textContent = '✕';
    x.addEventListener('click', async () => {
      await api(`/api/images/${img.id}/tags/${encodeURIComponent(tag)}`, { method: 'DELETE' });
      img.tags = img.tags.filter((t) => t !== tag);
      renderLbTags(img);
      refreshTags();
    });
    pill.appendChild(x);
    box.appendChild(pill);
  }
}

async function addTag(index, name) {
  const img = state.images[index];
  name = name.trim().toLowerCase();
  if (!img || !name) return;
  await api(`/api/images/${img.id}/tags`, { method: 'POST', body: { tag: name } });
  if (!img.tags.includes(name)) img.tags.push(name);
  renderLbTags(img);
  refreshTags();
}

$('#lb-tag-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    addTag(state.lightbox, e.target.value);
    e.target.value = '';
  }
});

$('#lb-autotag').addEventListener('click', async (e) => {
  const index = state.lightbox;
  const img = state.images[index];
  if (!img) return;
  const btn = e.currentTarget;
  btn.classList.add('busy');
  btn.disabled = true;
  try {
    const { tags } = await api(`/api/images/${img.id}/autotag`, { method: 'POST' });
    img.tags = [...new Set([...img.tags, ...tags])];
    renderLbTags(img);
    refreshTags();
  } catch (err) {
    alert(`自動タグ付けに失敗: ${err.message}`);
  } finally {
    btn.classList.remove('busy');
    btn.disabled = false;
  }
});

$('.lb-close').addEventListener('click', closeLightbox);
$('.lb-prev').addEventListener('click', () => setSelected(state.selected - 1));
$('.lb-next').addEventListener('click', () => setSelected(state.selected + 1));
$('#lightbox').addEventListener('click', (e) => {
  if (e.target === e.currentTarget) closeLightbox();
});

// ---- toolbar ----
let searchTimer = null;
$('#search').addEventListener('input', (e) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.filters.q = e.target.value.trim();
    loadImages(true);
  }, 300);
});

function bindRatingFilter(value) {
  renderStars($('#rating-filter'), value, (v) => {
    state.filters.minRating = v;
    bindRatingFilter(v);
    loadImages(true);
  }, true);
}
bindRatingFilter(0);

$('#toggle-rejected').addEventListener('click', (e) => {
  state.filters.rejected = !state.filters.rejected;
  e.currentTarget.classList.toggle('active', state.filters.rejected);
  loadImages(true);
});

$('#sort').addEventListener('change', (e) => {
  state.filters.sort = e.target.value;
  loadImages(true);
});

$('#rescan').addEventListener('click', async (e) => {
  const btn = e.currentTarget;
  btn.classList.add('busy');
  try {
    await api('/api/scan', { method: 'POST' });
    await Promise.all([loadImages(true), refreshFolders(), refreshTags()]);
  } finally {
    btn.classList.remove('busy');
  }
});

// ---- sidebar ----
async function refreshFolders() {
  const folders = await api('/api/folders');
  const ul = $('#folder-list');
  ul.innerHTML = '';
  for (const f of folders) {
    const li = document.createElement('li');
    const name = document.createElement('span');
    name.textContent = f.path;
    name.title = f.path;
    li.appendChild(name);
    const x = document.createElement('span');
    x.className = 'tag-x';
    x.textContent = '✕';
    x.title = 'このフォルダをライブラリから外す（ファイルは消えません）';
    x.addEventListener('click', async () => {
      if (!confirm(`ライブラリから外しますか？\n${f.path}\n（ディスク上のファイルは削除されません）`)) return;
      await api(`/api/folders/${f.id}`, { method: 'DELETE' });
      await Promise.all([loadImages(true), refreshFolders(), refreshTags()]);
    });
    li.appendChild(x);
    ul.appendChild(li);
  }
}

$('#add-folder').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = e.target.querySelector('input');
  try {
    await api('/api/folders', { method: 'POST', body: { path: input.value.trim() } });
    input.value = '';
    await Promise.all([loadImages(true), refreshFolders(), refreshTags()]);
  } catch (err) {
    alert(err.message);
  }
});

async function refreshTags() {
  const tags = await api('/api/tags');
  const ul = $('#tag-list');
  ul.innerHTML = '';
  for (const t of tags) {
    const li = document.createElement('li');
    li.textContent = `${t.name} (${t.count})`;
    li.classList.toggle('active', state.filters.tag === t.name);
    li.addEventListener('click', () => {
      state.filters.tag = state.filters.tag === t.name ? null : t.name;
      refreshTags();
      loadImages(true);
    });
    ul.appendChild(li);
  }
}

// ---- keyboard ----
document.addEventListener('keydown', (e) => {
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName);
  if (typing) {
    if (e.key === 'Escape') e.target.blur();
    return;
  }
  if (e.key === '/') {
    e.preventDefault();
    $('#search').focus();
    return;
  }
  if (e.key === 'Escape') {
    if (state.lightbox >= 0) closeLightbox();
    return;
  }
  if (state.selected < 0) return;

  switch (e.key) {
    case 'ArrowLeft':
      e.preventDefault();
      setSelected(state.selected - 1);
      break;
    case 'ArrowRight':
      e.preventDefault();
      setSelected(state.selected + 1);
      break;
    case 'ArrowUp':
      if (state.lightbox < 0) {
        e.preventDefault();
        moveVertical(1);
      }
      break;
    case 'ArrowDown':
      if (state.lightbox < 0) {
        e.preventDefault();
        moveVertical(-1);
      }
      break;
    case 'Enter':
      openLightbox(state.selected);
      break;
    case 'x':
    case 'X':
      toggleReject(state.selected);
      break;
    case 't':
    case 'T':
      e.preventDefault();
      if (state.lightbox < 0) openLightbox(state.selected);
      $('#lb-tag-input').focus();
      break;
    default:
      if (/^[0-5]$/.test(e.key)) rate(state.selected, Number(e.key));
  }
});

// ---- init ----
loadImages(true);
refreshFolders();
refreshTags();
