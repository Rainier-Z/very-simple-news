/* ─── State ─── */
let filters = {};
let debounceTimer = null;

/* ─── Init ─── */
document.addEventListener('DOMContentLoaded', async () => {
  loadTheme();
  await loadFilterOptions();
  const today = new Date().toISOString().split('T')[0];
  document.getElementById('dateFilter').value = today;
  filters.date = today;
  await loadNews();
  checkAutoRefresh();
  setInterval(pollStatus, 2000);
});

/* ─── Theme ─── */
function loadTheme() {
  const saved = localStorage.getItem('newsflow-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
}
function toggleTheme() {
  const html = document.documentElement;
  const cur = html.getAttribute('data-theme');
  const next = cur === 'light' ? 'dark' : 'light';
  html.setAttribute('data-theme', next);
  localStorage.setItem('newsflow-theme', next);
}

/* ─── Chip clicks ─── */
document.addEventListener('click', e => {
  const chip = e.target.closest('.chip');
  if (!chip) return;
  const group = chip.closest('.filter-chip-group');
  if (!group) return;
  group.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
  chip.classList.add('active');
  applyFilters();
});

/* ─── Apply filters ─── */
function applyFilters() {
  const catChip = document.querySelector('#categoryFilters .chip.active');
  const readChip = document.querySelector('#readFilters .chip.active');
  filters = {
    category: catChip?.dataset.category || '',
    source: document.getElementById('sourceFilter').value,
    read: readChip?.dataset.read || '',
    bookmarked: document.getElementById('bookmarkFilter').checked ? '1' : '',
    date: document.getElementById('dateFilter').value,
    q: document.getElementById('searchInput').value.trim(),
  };
  loadNews();
}

function debouncedSearch() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(applyFilters, 300);
}

/* ─── Load filter options ─── */
async function loadFilterOptions() {
  try {
    const r = await fetch('/api/filters');
    const d = await r.json();
    const sel = document.getElementById('sourceFilter');
    sel.innerHTML = '<option value="">全部来源</option>';
    d.sources.forEach(s => { sel.innerHTML += `<option value="${s}">${s}</option>`; });
    const catBox = document.getElementById('categoryFilters');
    d.categories.forEach(c => { catBox.innerHTML += `<button class="chip" data-category="${c}">${c}</button>`; });
  } catch(e) { console.error('filter load error', e); }
}

/* ─── Load news ─── */
async function loadNews() {
  const p = new URLSearchParams();
  Object.entries(filters).forEach(([k,v]) => { if (v) p.set(k, v); });
  try {
    const r = await fetch(`/api/news?${p}`);
    const d = await r.json();
    renderNews(d.news);
  } catch(e) {
    document.getElementById('newsList').innerHTML = '<div class="empty">加载失败，请重试</div>';
  }
  updateStats();
}

/* ─── Render ─── */
function renderNews(news) {
  const el = document.getElementById('newsList');
  if (!news.length) {
    el.innerHTML = '<div class="empty">暂无新闻</div>';
    document.getElementById('footer').textContent = '共 0 条';
    return;
  }
  let html = '';
  news.forEach(a => {
    const cls = ['news-card', a.is_read ? 'read' : '', a.is_bookmarked ? 'bookmarked' : ''].filter(Boolean).join(' ');
    html += `
      <div class="${cls}" data-id="${a.id}">
        <div class="card-meta">
          <span class="card-source">${esc(a.source)}</span>
          <span class="card-date">${esc(a.published_date)}</span>
          ${a.category ? `<span class="card-category">${esc(a.category)}</span>` : ''}
        </div>
        <div class="card-title" onclick="openNews('${a.id}','${escAttr(a.url)}')">${esc(a.title)}</div>
        ${a.summary ? `<div class="card-summary">${esc(a.summary)}</div>` : ''}
        <div class="card-actions">
          <button class="card-action bookmark-btn ${a.is_bookmarked ? 'active' : ''}" onclick="toggleBookmark('${a.id}')">${a.is_bookmarked ? '★' : '☆'}</button>
          <button class="card-action read-btn${a.is_read ? ' marked' : ''}" onclick="markRead('${a.id}')">${a.is_read ? '✓ 已读' : '○ 标为已读'}</button>
          <button class="card-action crawl-btn" onclick="crawlArticle('${a.id}')" id="crawl-${a.id}">🔍 要点总结</button>
          <button class="card-action save-btn" onclick="saveFull('${a.id}')" id="save-${a.id}">📄 爬取全文</button>
          <a href="${escAttr(a.url)}" target="_blank" class="card-action link-btn" rel="noopener">原文 →</a>
        </div>
        <div class="crawl-result" id="crawl-result-${a.id}" style="display:none"></div>
      </div>`;
  });
  el.innerHTML = html;
  document.getElementById('footer').textContent = `共 ${news.length} 条新闻`;
}

/* ─── Interactions ─── */
async function openNews(id, url) {
  await markRead(id);
  window.open(url, '_blank');
}
async function markRead(id) {
  try {
    await fetch(`/api/news/${id}/read`, { method: 'POST' });
    const card = document.querySelector(`.news-card[data-id="${id}"]`);
    if (card) {
      card.classList.remove('bookmarked'); // keep read style
      card.classList.add('read');
      const btn = card.querySelector('.read-btn');
      if (btn) { btn.textContent = '✓ 已读'; btn.classList.add('marked'); }
    }
    updateStats();
  } catch(e) { showToast('操作失败'); }
}
async function toggleBookmark(id) {
  try {
    const r = await fetch(`/api/news/${id}/bookmark`, { method: 'POST' });
    const d = await r.json();
    const card = document.querySelector(`.news-card[data-id="${id}"]`);
    if (card) {
      const btn = card.querySelector('.bookmark-btn');
      btn.textContent = d.bookmarked ? '★' : '☆';
      btn.classList.toggle('active', d.bookmarked);
      card.classList.toggle('bookmarked', d.bookmarked);
    }
  } catch(e) { showToast('操作失败'); }
}

/* ─── Refresh ─── */
async function refreshNews() {
  const btn = document.getElementById('refreshBtn');
  btn.disabled = true; btn.textContent = '收集中…';
  document.getElementById('progressBar').style.display = 'block';
  try {
    const r = await fetch('/api/refresh', { method: 'POST' });
    const d = await r.json();
    if (d.status === 'already_running') showToast('正在收集中，请稍候…');
  } catch(e) { showToast('刷新失败'); btn.disabled = false; btn.textContent = '刷新'; }
}

/* ─── Poll status ─── */
async function pollStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const bar = document.getElementById('progressBar');
    const fill = document.getElementById('progressFill');
    const txt = document.getElementById('progressText');
    const btn = document.getElementById('refreshBtn');

    if (d.collecting) {
      bar.style.display = 'block';
      const done = d.progress.filter(p => p.status === 'ok' || p.status === 'fail').length;
      const pct = Math.min((done / 7) * 100, 100); // 7 sources
      fill.style.width = pct + '%';
      const last = d.progress[d.progress.length - 1];
      txt.textContent = last ? `${last.source}: ${last.detail}` : '正在获取…';
      btn.disabled = true; btn.textContent = '收集中…';
    } else {
      if (bar.style.display !== 'none') {
        fill.style.width = '100%';
        setTimeout(() => { bar.style.display = 'none'; }, 800);
        showToast('新闻更新完成');
        await loadNews(); await loadFilterOptions();
      }
      btn.disabled = false; btn.textContent = '刷新';
    }
  } catch(e) { /* ignore */ }
}

/* ─── Auto refresh on first load if empty ─── */
async function checkAutoRefresh() {
  try {
    const sr = await fetch('/api/stats');
    const s = await sr.json();
    if (s.today === 0) { showToast('正在获取今日新闻…'); refreshNews(); }
  } catch(e) {}
}

/* ─── Stats ─── */
async function updateStats() {
  try {
    const r = await fetch('/api/stats');
    const d = await r.json();
    document.getElementById('statsBar').textContent = `今日 ${d.today} · 未读 ${d.unread} · 收藏 ${d.bookmarked}`;
  } catch(e) {}
}

/* ─── Crawl ─── */
async function crawlArticle(id) {
  const btn = document.getElementById(`crawl-${id}`);
  const resultDiv = document.getElementById(`crawl-result-${id}`);
  if (resultDiv.style.display === 'block') {
    resultDiv.style.display = 'none';
    btn.textContent = '🔍 深度爬取';
    return;
  }
  btn.disabled = true;
  btn.textContent = '⏳ 爬取中…';
  resultDiv.style.display = 'block';
  resultDiv.innerHTML = '<div class="crawl-loading">正在获取全文并分析…</div>';
  try {
    const r = await fetch(`/api/news/${id}/crawl`, { method: 'POST' });
    const d = await r.json();
    if (d.error) {
      resultDiv.innerHTML = `<div class="crawl-error">${d.error}</div>`;
      btn.textContent = '🔍 重试';
    } else {
      let analysis = d.analysis;
      if (typeof analysis === 'string') {
        try { analysis = JSON.parse(analysis); } catch(e) {}
      }
      let html = '';
      if (analysis && analysis.summary) {
        html += `<div class="crawl-section"><span class="crawl-label">核心摘要</span><p>${esc(analysis.summary)}</p></div>`;
      }
      if (analysis && analysis.key_points) {
        html += `<div class="crawl-section"><span class="crawl-label">关键要点</span><ul>`;
        analysis.key_points.forEach(p => { html += `<li>${esc(p)}</li>`; });
        html += `</ul></div>`;
      }
      if (analysis && analysis.background) {
        html += `<div class="crawl-section"><span class="crawl-label">背景信息</span><p>${esc(analysis.background)}</p></div>`;
      }
      if (analysis && analysis.related_topics) {
        html += `<div class="crawl-section"><span class="crawl-label">相关话题</span><div class="crawl-tags">`;
        analysis.related_topics.forEach(t => { html += `<span class="crawl-tag">${esc(t)}</span>`; });
        html += `</div></div>`;
      }
      if (!html) html = '<div class="crawl-error">分析结果格式异常</div>';
      resultDiv.innerHTML = html;
      btn.textContent = '🔍 收起';
    }
  } catch(e) {
    resultDiv.innerHTML = '<div class="crawl-error">网络错误</div>';
    btn.textContent = '🔍 重试';
  }
  btn.disabled = false;
}

/* ─── Save Full Article ─── */
async function saveFull(id) {
  const btn = document.getElementById(`save-${id}`);
  btn.disabled = true;
  btn.textContent = '⏳ 保存中…';
  try {
    const r = await fetch(`/api/news/${id}/save-full`, { method: 'POST' });
    const d = await r.json();
    if (d.ok) {
      showToast(`已保存 → ${d.path}`);
      btn.textContent = '✅ 已保存';
    } else {
      showToast(d.error || '保存失败');
      btn.textContent = '📄 爬取全文';
    }
  } catch(e) {
    showToast('网络错误');
    btn.textContent = '📄 爬取全文';
  }
  btn.disabled = false;
}

/* ─── Helpers ─── */
function esc(t) {
  const el = document.createElement('div');
  el.textContent = t;
  return el.innerHTML;
}
function escAttr(u) {
  return u.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(t._hide);
  t._hide = setTimeout(() => t.classList.remove('show'), 2500);
}
