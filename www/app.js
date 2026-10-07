// ============================================================
// Budget Book Panel — main app
// ============================================================

const $ = (id) => document.getElementById(id);
const fmt = (n) => n == null ? '—' : Math.round(n).toLocaleString();
const fmtSigned = (n) => n == null ? '—' : (n >= 0 ? '+' : '') + Math.round(n).toLocaleString();

function log(...args) {
  console.log('[BudgetBook]', ...args);
  try { if (window._bb_logs) window._bb_logs.push(args.map(a => String(a)).join(' ')); } catch(e){}
}
window._bb_logs = [];

let parentHass = null;
let states = {};
let charts = {};
let modalTxType = 'expense';
let modalTxCategory = null;
let editingTxId = null;
let modalCatType = 'expense';

// ============================================================
// Connection
// ============================================================

async function getParentHass(maxWaitMs = 10000) {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    try {
      const parentDoc = window.parent.document;
      const haEl = parentDoc.querySelector('home-assistant');
      if (haEl && haEl.hass && haEl.hass.states) {
        return haEl.hass;
      }
    } catch (e) {}
    await new Promise(r => setTimeout(r, 200));
  }
  return null;
}

async function getAuthToken() {
  // 1) From the parent HA frontend's live auth object (works in browser and Companion app)
  try {
    const hass = parentHass || await getParentHass(3000);
    const auth = hass && (hass.auth || hass.connection?.options?.auth);
    if (auth) {
      if (auth.expired && typeof auth.refreshAccessToken === 'function') {
        try { await auth.refreshAccessToken(); } catch (e) {}
      }
      const t = auth.accessToken || auth.data?.access_token;
      if (t) return t;
    }
  } catch (e) {}
  // 2) Fallback: tokens stored by the browser frontend
  for (const ls of [() => window.parent.localStorage, () => localStorage]) {
    try {
      const tokens = ls().getItem('hassTokens');
      if (tokens) return JSON.parse(tokens).access_token;
    } catch (e) {}
  }
  return null;
}

async function callService(domain, service, data = {}) {
  // Prefer the parent frontend's websocket connection: no token needed,
  // and it works in the HA Companion app (which uses external auth, no hassTokens).
  const hass = parentHass || await getParentHass(3000);
  if (hass && typeof hass.callService === 'function') {
    return await hass.callService(domain, service, data);
  }
  const token = await getAuthToken();
  if (!token) throw new Error('No auth token');
  const resp = await fetch(`/api/services/${domain}/${service}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Service call failed: ${resp.status} ${text}`);
  }
  return await resp.json();
}

function syncStates() {
  if (!parentHass || !parentHass.states) return;
  states = {};
  for (const [eid, st] of Object.entries(parentHass.states)) {
    states[eid] = st;
  }
}

function showError(msg) {
  $('loading').style.display = 'none';
  $('main').style.display = 'none';
  $('error').style.display = 'block';
  $('error-msg').textContent = msg;
}

async function connectHA() {
  try {
    log('Connecting...');
    parentHass = await getParentHass(8000);
    if (!parentHass) {
      throw new Error('找不到 home-assistant 元素。請從 HA 側邊欄開啟。');
    }
    syncStates();
    log('Connected. States:', Object.keys(states).length);

    // Sanity check
    if (!states['sensor.budget_book_all_books']) {
      throw new Error('找不到 sensor.budget_book_all_books。請確認整合已新增並重啟 HA。');
    }

    // Poll for changes every 3s
    setInterval(() => {
      if (!parentHass) return;
      const prev = JSON.stringify(states['sensor.budget_book_all_books']?.attributes?.full_data || {});
      const next = JSON.stringify(parentHass.states['sensor.budget_book_all_books']?.attributes?.full_data || {});
      if (prev !== next) {
        syncStates();
        render();
      }
    }, 3000);

    return true;
  } catch (e) {
    log('Connection failed:', e.message);
    showError('連線失敗:' + e.message);
    return false;
  }
}

// ============================================================
// Data accessors
// ============================================================

function getData() {
  const st = states['sensor.budget_book_all_books'];
  if (!st || !st.attributes || !st.attributes.full_data) {
    return { books: {}, active_book_id: null };
  }
  return st.attributes.full_data;
}

function getActiveBook() {
  const data = getData();
  const id = data.active_book_id;
  return id ? data.books[id] : null;
}

function getMonthMetrics() {
  const st = states['sensor.budget_book_month_expense'];
  if (!st || !st.attributes) return null;
  const expense = parseFloat(states['sensor.budget_book_month_expense']?.state) || 0;
  const income = parseFloat(states['sensor.budget_book_month_income']?.state) || 0;
  const balance = parseFloat(states['sensor.budget_book_month_balance']?.state) || 0;
  const totalBalance = parseFloat(states['sensor.budget_book_balance']?.state) || 0;
  const txCount = parseInt(states['sensor.budget_book_transaction_count']?.state) || 0;
  return {
    month_expense: expense,
    month_income: income,
    month_balance: balance,
    balance: totalBalance,
    transaction_count: txCount,
    month_label: st.attributes.month_label || '',
    this_month_count: st.attributes.this_month_count || 0,
    category_breakdown: st.attributes.category_breakdown || [],
    budget_alerts: st.attributes.budget_alerts || [],
  };
}

// ============================================================
// Render
// ============================================================

function render() {
  try {
    renderBookSwitcher();
    renderHome();
    renderTransactions();
    renderCharts();
    renderCategories();
    renderBudgets();
    renderRecurring();
    renderSettings();
  } catch (e) {
    log('Render error:', e.message, e.stack);
  }
}

function renderBookSwitcher() {
  const data = getData();
  const sw = $('book-switcher');
  sw.innerHTML = '';
  for (const [id, book] of Object.entries(data.books)) {
    const opt = document.createElement('option');
    opt.value = id;
    opt.textContent = book.name;
    if (id === data.active_book_id) opt.selected = true;
    sw.appendChild(opt);
  }
}

function renderHome() {
  const m = getMonthMetrics();
  if (!m) return;
  $('m-month-expense').textContent = fmt(m.month_expense);
  $('m-month-income').textContent = fmt(m.month_income);
  $('m-month-label').textContent = m.month_label;
  $('m-tx-count').textContent = `總計 ${m.transaction_count} 筆`;

  const bEl = $('m-month-balance');
  bEl.textContent = fmtSigned(m.month_balance);
  bEl.className = 'metric-value ' + (m.month_balance >= 0 ? 'positive' : 'negative');

  const tEl = $('m-balance');
  tEl.textContent = fmtSigned(m.balance);
  tEl.className = 'metric-value ' + (m.balance >= 0 ? 'positive' : 'negative');

  // Budget banner
  const overCount = (m.budget_alerts || []).filter(a => a.severity === 'over').length;
  const warnCount = (m.budget_alerts || []).filter(a => a.severity === 'warning').length;
  let banner = '';
  if (overCount > 0) {
    const names = m.budget_alerts.filter(a => a.severity === 'over').map(a => a.category_name).join('、');
    banner = `<div class="banner banner-over"><div class="banner-title">⚠️ ${overCount} 個類別超支</div>已超支:${names}</div>`;
  } else if (warnCount > 0) {
    const names = m.budget_alerts.filter(a => a.severity === 'warning').map(a => `${a.category_name}(${a.pct}%)`).join('、');
    banner = `<div class="banner banner-warning"><div class="banner-title">⚠️ ${warnCount} 個類別預算警戒</div>${names}</div>`;
  }
  $('budget-banner').innerHTML = banner;

  // Category list
  const catEl = $('home-categories');
  const cats = m.category_breakdown || [];
  if (cats.length === 0) {
    catEl.innerHTML = '<div class="empty">本月還沒有支出紀錄</div>';
  } else {
    catEl.innerHTML = cats.slice(0, 8).map(c => {
      let barClass = '';
      let barWidth = 0;
      if (c.budget) {
        barWidth = Math.min(100, c.usage_pct);
        if (c.usage_pct >= 100) barClass = 'over';
        else if (c.usage_pct >= 80) barClass = 'warn';
      } else {
        barWidth = Math.min(100, (c.amount / cats[0].amount) * 100);
      }
      const budgetStr = c.budget
        ? `<span class="category-meta">${fmt(c.amount)} / ${fmt(c.budget)} (${c.usage_pct}%)</span>`
        : `<span class="category-meta">${c.count} 筆</span>`;
      return `
        <div class="category-row">
          <span class="cat-color-dot" style="background:${c.color || '#999'}"></span>
          <div class="category-info">
            <div class="category-name">${c.name}</div>
            ${budgetStr}
          </div>
          <div class="category-bar-wrap">
            <div class="category-bar-fill ${barClass}" style="width:${barWidth}%"></div>
          </div>
          <div class="category-amount">${fmt(c.amount)}</div>
        </div>
      `;
    }).join('');
  }

  // Upcoming recurring
  const book = getActiveBook();
  const upcomingEl = $('home-upcoming');
  const recurring = (book?.recurring || []).filter(r => r.active);
  if (recurring.length === 0) {
    upcomingEl.innerHTML = '<div class="empty">尚未設定固定支出</div>';
  } else {
    const today = new Date();
    const upcoming = recurring.map(r => {
      const day = Math.min(r.day_of_month, 28);
      let due = new Date(today.getFullYear(), today.getMonth(), day);
      if (due < today) {
        due = new Date(today.getFullYear(), today.getMonth() + 1, day);
      }
      const daysUntil = Math.ceil((due - today) / 86400000);
      return { ...r, due, daysUntil };
    }).sort((a, b) => a.daysUntil - b.daysUntil).slice(0, 5);

    upcomingEl.innerHTML = upcoming.map(r => {
      let badge = '';
      if (r.daysUntil <= 0) badge = '<span class="badge badge-today">今天</span>';
      else if (r.daysUntil <= 3) badge = `<span class="badge badge-soon">${r.daysUntil} 天後</span>`;
      else badge = `<span class="badge">${r.daysUntil} 天後</span>`;
      const catName = getCatName(book, r.category);
      return `
        <div class="upcoming-row">
          <div>
            <div class="upcoming-name">${r.name} ${badge}</div>
            <div class="upcoming-meta">${r.due.toISOString().slice(0,10)} · ${catName}</div>
          </div>
          <div class="upcoming-amount ${r.type}">${r.type === 'expense' ? '-' : '+'}${fmt(r.amount)}</div>
        </div>
      `;
    }).join('');
  }

  // Recent transactions
  const recentEl = $('home-recent-tbody');
  const txs = [...(book?.transactions || [])].sort((a, b) => txSortKey(b).localeCompare(txSortKey(a))).slice(0, 8);
  if (txs.length === 0) {
    recentEl.innerHTML = '<tr><td colspan="4" class="empty">無交易紀錄</td></tr>';
  } else {
    recentEl.innerHTML = txs.map(t => {
      const cat = book.categories.find(c => c.id === t.category);
      const catBadge = cat
        ? `<span style="display:inline-flex;align-items:center;gap:4px"><span class="cat-color-dot" style="background:${cat.color}"></span>${cat.name}</span>`
        : t.category;
      const sign = t.type === 'expense' ? '-' : '+';
      const cls = t.type === 'expense' ? 'negative' : 'positive';
      return `
        <tr>
          <td>${fmtTxDate(t)}</td>
          <td>${catBadge}</td>
          <td style="text-align:right" class="${cls}">${sign}${fmt(t.amount)}</td>
          <td style="color:var(--text-secondary)">${t.note || '—'}</td>
        </tr>
      `;
    }).join('');
  }
}

function getCatName(book, catId) {
  if (!book) return catId;
  const c = book.categories.find(c => c.id === catId);
  return c ? c.name : catId;
}

function renderTransactions() {
  const book = getActiveBook();
  if (!book) return;

  // Populate filters
  const catFilter = $('tx-cat-filter');
  const currentCat = catFilter.value;
  catFilter.innerHTML = '<option value="">全部分類</option>';
  book.categories.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.name;
    catFilter.appendChild(opt);
  });
  catFilter.value = currentCat;

  // Month filter
  const monthFilter = $('tx-month-filter');
  const currentMonth = monthFilter.value;
  const months = [...new Set(book.transactions.map(t => t.date.slice(0, 7)))].sort().reverse();
  monthFilter.innerHTML = '<option value="">全部月份</option>' +
    months.map(m => `<option value="${m}">${m}</option>`).join('');
  monthFilter.value = currentMonth;

  applyTxFilters();
}

function applyTxFilters() {
  const book = getActiveBook();
  if (!book) return;
  const search = $('tx-filter').value.toLowerCase();
  const typeF = $('tx-type-filter').value;
  const catF = $('tx-cat-filter').value;
  const monthF = $('tx-month-filter').value;

  let filtered = book.transactions.filter(t => {
    if (typeF && t.type !== typeF) return false;
    if (catF && t.category !== catF) return false;
    if (monthF && !t.date.startsWith(monthF)) return false;
    if (search) {
      const blob = `${t.date} ${t.amount} ${t.note || ''} ${getCatName(book, t.category)}`.toLowerCase();
      if (!blob.includes(search)) return false;
    }
    return true;
  }).sort((a, b) => txSortKey(b).localeCompare(txSortKey(a)));

  const tbody = $('tx-tbody');
  if (filtered.length === 0) {
    tbody.innerHTML = '';
    $('tx-empty').style.display = 'block';
    $('tx-empty').textContent = book.transactions.length ? '無符合條件的交易' : '尚無交易';
  } else {
    $('tx-empty').style.display = 'none';
    tbody.innerHTML = filtered.map(t => {
      const cat = book.categories.find(c => c.id === t.category);
      const catBadge = cat
        ? `<span style="display:inline-flex;align-items:center;gap:4px"><span class="cat-color-dot" style="background:${cat.color}"></span>${cat.name}</span>`
        : t.category;
      const sign = t.type === 'expense' ? '-' : '+';
      const cls = t.type === 'expense' ? 'negative' : 'positive';
      const typeBadge = `<span class="badge badge-${t.type}">${t.type === 'expense' ? '支出' : '收入'}</span>`;
      return `
        <tr>
          <td>${fmtTxDate(t)}</td>
          <td>${typeBadge}</td>
          <td>${catBadge}</td>
          <td style="text-align:right" class="${cls}">${sign}${fmt(t.amount)}</td>
          <td style="color:var(--text-secondary)">${t.note || '—'}</td>
          <td><button class="del-btn" data-tx-id="${t.id}">×</button></td>
        </tr>
      `;
    }).join('');

    tbody.querySelectorAll('.del-btn').forEach(b => {
      b.onclick = async () => {
        if (!confirm('確定刪除這筆交易?')) return;
        try {
          await callService('budget_book', 'delete_transaction', { transaction_id: b.dataset.txId });
        } catch (e) { alert('刪除失敗:' + e.message); }
      };
    });
  }
}

function renderCharts() {
  if (!window.Chart) return;
  if (!$('tab-charts').classList.contains('active')) return;
  const book = getActiveBook();
  if (!book) return;

  // Compute trend manually (no need for server)
  const today = new Date();
  const trendData = [];
  for (let offset = 5; offset >= 0; offset--) {
    const d = new Date(today.getFullYear(), today.getMonth() - offset, 1);
    const y = d.getFullYear(), m = d.getMonth() + 1;
    const prefix = `${y}-${String(m).padStart(2, '0')}`;
    const mTxs = book.transactions.filter(t => t.date.startsWith(prefix));
    trendData.push({
      label: prefix,
      income: mTxs.filter(t => t.type === 'income').reduce((s, t) => s + t.amount, 0),
      expense: mTxs.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0),
    });
  }

  const opts = chartOpts();

  drawChart('chart-trend', {
    type: 'bar',
    data: {
      labels: trendData.map(d => d.label),
      datasets: [
        { label: '收入', data: trendData.map(d => d.income), backgroundColor: '#27AE60' },
        { label: '支出', data: trendData.map(d => d.expense), backgroundColor: '#E74C3C' },
      ]
    },
    options: opts.bar
  });

  // Pie: this month's expense by category
  const m = getMonthMetrics();
  const breakdown = (m?.category_breakdown || []).slice(0, 10);
  if (breakdown.length > 0) {
    drawChart('chart-pie', {
      type: 'doughnut',
      data: {
        labels: breakdown.map(c => c.name),
        datasets: [{
          data: breakdown.map(c => c.amount),
          backgroundColor: breakdown.map(c => c.color || '#999'),
          borderWidth: 2,
          borderColor: getComputedStyle(document.body).getPropertyValue('--bg').trim() || '#fff'
        }]
      },
      options: opts.pie
    });
  }

  // Budget bar
  const alerts = m?.budget_alerts || [];
  if (alerts.length > 0) {
    drawChart('chart-budgets', {
      type: 'bar',
      data: {
        labels: alerts.map(a => a.category_name),
        datasets: [{
          label: '使用率 %',
          data: alerts.map(a => a.pct),
          backgroundColor: alerts.map(a => {
            if (a.severity === 'over') return '#E74C3C';
            if (a.severity === 'warning') return '#F39C12';
            return '#27AE60';
          }),
        }]
      },
      options: { ...opts.bar, indexAxis: 'y' }
    });
  }
}

function chartOpts() {
  const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const textColor = isDark ? '#b0b0b0' : '#6b6b6b';
  const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
  return {
    bar: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: textColor } },
      },
      scales: {
        x: { ticks: { color: textColor }, grid: { color: gridColor } },
        y: { ticks: { color: textColor }, grid: { color: gridColor } }
      }
    },
    pie: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { color: textColor, font: { size: 11 } } },
      }
    }
  };
}

function drawChart(id, config) {
  const c = $(id);
  if (!c) return;
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(c, config);
}

function renderCategories() {
  const book = getActiveBook();
  if (!book) return;
  const expEl = $('cat-list-expense');
  const incEl = $('cat-list-income');
  const renderList = (list) => {
    if (list.length === 0) return '<div class="empty">尚無分類</div>';
    // Don't allow deleting the last category of a type
    const canDelete = list.length > 1;
    return list.map(c => `
      <div class="chip cat-chip" title="${c.id}">
        <span class="chip-dot" style="background:${c.color}"></span>${c.name}
        ${canDelete ? `<button class="cat-del-btn" data-del-cat="${c.id}" data-del-name="${c.name}" title="刪除分類">×</button>` : ''}
      </div>
    `).join('');
  };
  expEl.innerHTML = renderList(book.categories.filter(c => c.type === 'expense'));
  incEl.innerHTML = renderList(book.categories.filter(c => c.type === 'income'));

  document.querySelectorAll('#tab-categories [data-del-cat]').forEach(b => {
    b.onclick = async (ev) => {
      ev.stopPropagation();
      if (!confirm(`刪除分類「${b.dataset.delName}」?\n\n此分類的預算設定會一併移除,原有交易會改歸到「其他」。`)) return;
      try {
        await callService('budget_book', 'delete_category', { category: b.dataset.delCat });
      } catch (e) { alert('刪除失敗:' + e.message); }
    };
  });
}

function renderBudgets() {
  const book = getActiveBook();
  if (!book) return;
  const m = getMonthMetrics();
  const el = $('budget-list');

  const expCats = book.categories.filter(c => c.type === 'expense');
  el.innerHTML = expCats.map(c => {
    const limit = book.budgets[c.id];
    const breakdown = (m?.category_breakdown || []).find(b => b.category_id === c.id);
    const spent = breakdown?.amount || 0;
    let progressClass = '';
    let pct = 0;
    let amountStr = '';
    if (limit) {
      pct = Math.min(100, (spent / limit) * 100);
      const realPct = (spent / limit) * 100;
      if (realPct >= 100) progressClass = 'over';
      else if (realPct >= 80) progressClass = 'warn';
      amountStr = `本月已花 ${fmt(spent)} / 上限 ${fmt(limit)} (${realPct.toFixed(0)}%)`;
    } else {
      amountStr = `本月已花 ${fmt(spent)} · <em style="color:var(--text-muted)">尚未設定預算</em>`;
    }
    return `
      <div class="budget-row">
        <span class="cat-color-dot" style="background:${c.color}"></span>
        <div class="budget-info">
          <div style="font-weight:500">${c.name}</div>
          <div class="budget-progress"><div class="budget-progress-fill ${progressClass}" style="width:${pct}%"></div></div>
          <div class="budget-amount-display">${amountStr}</div>
        </div>
        <button class="btn-secondary" data-budget-cat="${c.id}" data-budget-name="${c.name}" data-budget-limit="${limit || ''}">設定</button>
      </div>
    `;
  }).join('');

  el.querySelectorAll('[data-budget-cat]').forEach(b => {
    b.onclick = () => openBudgetModal(b.dataset.budgetCat, b.dataset.budgetName, b.dataset.budgetLimit);
  });
}

function renderRecurring() {
  const book = getActiveBook();
  if (!book) return;
  const tbody = $('recurring-tbody');
  const rules = book.recurring || [];
  if (rules.length === 0) {
    tbody.innerHTML = '';
    $('recurring-empty').style.display = 'block';
  } else {
    $('recurring-empty').style.display = 'none';
    tbody.innerHTML = rules.map(r => {
      const cat = book.categories.find(c => c.id === r.category);
      const catName = cat ? cat.name : r.category;
      const typeBadge = `<span class="badge badge-${r.type}">${r.type === 'expense' ? '支出' : '收入'}</span>`;
      const lastRun = r.last_run_date || '<span style="color:var(--text-muted)">未執行</span>';
      const sign = r.type === 'expense' ? '-' : '+';
      const cls = r.type === 'expense' ? 'negative' : 'positive';
      return `
        <tr>
          <td>${r.name}${r.note ? `<div style="font-size:11px;color:var(--text-muted)">${r.note}</div>` : ''}</td>
          <td>${typeBadge}</td>
          <td>${catName}</td>
          <td style="text-align:right" class="${cls}">${sign}${fmt(r.amount)}</td>
          <td style="text-align:center">${r.day_of_month} 號</td>
          <td>${lastRun}</td>
          <td><button class="del-btn" data-rec-id="${r.id}">×</button></td>
        </tr>
      `;
    }).join('');

    tbody.querySelectorAll('.del-btn').forEach(b => {
      b.onclick = async () => {
        if (!confirm('刪除此固定支出規則?(已建立的交易不會刪除)')) return;
        try { await callService('budget_book', 'delete_recurring', { recurring_id: b.dataset.recId }); }
        catch (e) { alert('刪除失敗:' + e.message); }
      };
    });
  }
}

function renderSettings() {
  const data = getData();
  const tbody = $('books-tbody');
  tbody.innerHTML = Object.values(data.books).map(b => {
    const isActive = b.id === data.active_book_id;
    return `
      <tr>
        <td>${b.name}${isActive ? ' <span class="badge badge-today">使用中</span>' : ''}</td>
        <td>${b.currency || 'TWD'}</td>
        <td>${b.transaction_count}</td>
        <td>
          <button class="btn-secondary" data-book-rename="${b.id}" data-book-name="${b.name}">改名</button>
          ${!isActive ? `<button class="btn-secondary" data-book-activate="${b.id}">切換</button>` : ''}
          ${Object.keys(data.books).length > 1 ? `<button class="btn-danger" data-book-delete="${b.id}" data-book-name="${b.name}">刪除</button>` : ''}
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('[data-book-rename]').forEach(b => {
    b.onclick = async () => {
      const name = prompt('新名稱:', b.dataset.bookName);
      if (name && name !== b.dataset.bookName) {
        try { await callService('budget_book', 'rename_book', { book_id: b.dataset.bookRename, name }); }
        catch (e) { alert('改名失敗:' + e.message); }
      }
    };
  });
  tbody.querySelectorAll('[data-book-activate]').forEach(b => {
    b.onclick = async () => {
      try { await callService('budget_book', 'set_active_book', { book_id: b.dataset.bookActivate }); }
      catch (e) { alert('切換失敗:' + e.message); }
    };
  });
  tbody.querySelectorAll('[data-book-delete]').forEach(b => {
    b.onclick = async () => {
      if (!confirm(`確定刪除「${b.dataset.bookName}」?此記帳本的所有交易都會被清除,不可復原!`)) return;
      try { await callService('budget_book', 'delete_book', { book_id: b.dataset.bookDelete }); }
      catch (e) { alert('刪除失敗:' + e.message); }
    };
  });
}

// ============================================================
// Modals
// ============================================================

function openModal(id) {
  $(id).style.display = 'flex';
}

function closeModal(id) {
  $(id).style.display = 'none';
}

// ---- Time helpers (stored as 24h "HH:MM") ----
function initTimePicker() {
  $('tx-hour').innerHTML = Array.from({ length: 12 }, (_, i) => i + 1)
    .map(h => `<option value="${h}">${h}</option>`).join('');
  $('tx-minute').innerHTML = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, '0'))
    .map(m => `<option value="${m}">${m}</option>`).join('');
}

function setTimePicker(d) {
  if (!$('tx-hour').options.length) initTimePicker();
  const h24 = d.getHours();
  $('tx-ampm').value = h24 < 12 ? 'am' : 'pm';
  $('tx-hour').value = String(h24 % 12 === 0 ? 12 : h24 % 12);
  $('tx-minute').value = String(d.getMinutes()).padStart(2, '0');
}

function getTimePicker() {
  let h = parseInt($('tx-hour').value, 10) % 12;
  if ($('tx-ampm').value === 'pm') h += 12;
  return `${String(h).padStart(2, '0')}:${$('tx-minute').value}`;
}

function fmtTime(t) {
  if (!t) return '';
  const [h, m] = t.split(':').map(Number);
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h < 12 ? '上午' : '下午'} ${h12}:${String(m).padStart(2, '0')}`;
}

function txSortKey(t) {
  return `${t.date} ${t.time || ''}`;
}

function fmtTxDate(t) {
  return t.time ? `${t.date}<div class="tx-time">${fmtTime(t.time)}</div>` : t.date;
}

function localDateStr(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function openTxModal() {
  modalTxType = 'expense';
  modalTxCategory = null;
  editingTxId = null;
  $('modal-tx-title').textContent = '新增交易';
  $('tx-amount').value = '';
  $('tx-note').value = '';
  const now = new Date();
  $('tx-date').value = localDateStr(now);
  setTimePicker(now);
  document.querySelectorAll('.tx-type-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.type === 'expense');
  });
  renderCatPicker();
  openModal('modal-tx');
  setTimeout(() => $('tx-amount').focus(), 100);
}

function renderCatPicker() {
  const book = getActiveBook();
  if (!book) return;
  const cats = book.categories.filter(c => c.type === modalTxType);
  const picker = $('tx-cat-picker');
  picker.innerHTML = cats.map(c => `
    <div class="chip ${modalTxCategory === c.id ? 'selected' : ''}" data-cat="${c.id}">
      <span class="chip-dot" style="background:${c.color}"></span>${c.name}
    </div>
  `).join('');
  picker.querySelectorAll('.chip').forEach(ch => {
    ch.onclick = () => {
      modalTxCategory = ch.dataset.cat;
      picker.querySelectorAll('.chip').forEach(x => x.classList.toggle('selected', x.dataset.cat === modalTxCategory));
    };
  });
  // Auto-select first
  if (!modalTxCategory && cats.length > 0) {
    modalTxCategory = cats[0].id;
    picker.querySelector('.chip').classList.add('selected');
  }
}

function openBookModal() {
  $('book-name').value = '';
  $('book-currency').value = 'TWD';
  $('modal-book-title').textContent = '新增記帳本';
  openModal('modal-book');
  setTimeout(() => $('book-name').focus(), 100);
}

function openRecurringModal() {
  const book = getActiveBook();
  if (!book) return;
  $('rec-name').value = '';
  $('rec-type').value = 'expense';
  $('rec-amount').value = '';
  $('rec-day').value = '1';
  $('rec-note').value = '';
  const catSel = $('rec-category');
  catSel.innerHTML = book.categories.filter(c => c.type === 'expense')
    .map(c => `<option value="${c.id}">${c.name}</option>`).join('');
  openModal('modal-recurring');
}

function openBudgetModal(catId, catName, limit) {
  $('budget-cat-id').value = catId;
  $('budget-cat-label').textContent = `分類:${catName}`;
  $('budget-amount').value = limit || '';
  openModal('modal-budget');
  setTimeout(() => $('budget-amount').focus(), 100);
}

function openCatModal(type) {
  modalCatType = type;
  $('modal-cat-title').textContent = type === 'income' ? '新增收入分類' : '新增支出分類';
  $('cat-name').value = '';
  $('cat-icon').value = '';
  $('cat-color').value = type === 'income' ? '#27AE60' : '#E67E22';
  openModal('modal-cat');
  setTimeout(() => $('cat-name').focus(), 100);
}

// ============================================================
// Events
// ============================================================

function bindEvents() {
  // Tabs
  document.querySelectorAll('.tab').forEach(t => {
    t.onclick = () => {
      document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      $(`tab-${t.dataset.tab}`).classList.add('active');
      render();
    };
  });

  // Modal close buttons
  document.querySelectorAll('[data-close]').forEach(b => {
    b.onclick = () => closeModal(b.dataset.close);
  });

  // Book switcher
  $('book-switcher').onchange = async (e) => {
    try { await callService('budget_book', 'set_active_book', { book_id: e.target.value }); }
    catch (err) { alert('切換失敗:' + err.message); }
  };

  // Quick add
  $('btn-quick-add').onclick = openTxModal;

  // TX type switch in modal
  document.querySelectorAll('.tx-type-btn').forEach(b => {
    b.onclick = () => {
      modalTxType = b.dataset.type;
      modalTxCategory = null;
      document.querySelectorAll('.tx-type-btn').forEach(x => x.classList.toggle('active', x === b));
      renderCatPicker();
    };
  });

  $('tx-submit').onclick = async () => {
    const amount = parseFloat($('tx-amount').value);
    const date = $('tx-date').value;
    const time = getTimePicker();
    const note = $('tx-note').value;
    if (!amount || amount <= 0) { alert('請輸入金額'); return; }
    if (!date) { alert('請選擇日期'); return; }
    if (!modalTxCategory) { alert('請選擇分類'); return; }
    try {
      await callService('budget_book', 'add_transaction', {
        date, time, type: modalTxType, amount, category: modalTxCategory, note
      });
      closeModal('modal-tx');
    } catch (e) { alert('新增失敗:' + e.message); }
  };

  // TX filters
  ['tx-filter', 'tx-type-filter', 'tx-cat-filter', 'tx-month-filter'].forEach(id => {
    const el = $(id);
    if (el) el.addEventListener('input', applyTxFilters);
    if (el) el.addEventListener('change', applyTxFilters);
  });

  // Budgets
  $('budget-submit').onclick = async () => {
    const catId = $('budget-cat-id').value;
    const amount = parseFloat($('budget-amount').value) || 0;
    try {
      await callService('budget_book', 'set_budget', {
        category: catId, amount: amount > 0 ? amount : null
      });
      closeModal('modal-budget');
    } catch (e) { alert('儲存失敗:' + e.message); }
  };

  // Categories
  $('btn-add-cat-expense').onclick = () => openCatModal('expense');
  $('btn-add-cat-income').onclick = () => openCatModal('income');
  $('cat-submit').onclick = async () => {
    const name = $('cat-name').value.trim();
    const color = $('cat-color').value;
    const icon = $('cat-icon').value.trim();
    if (!name) { alert('請輸入分類名稱'); return; }
    const payload = { name, type: modalCatType, color };
    if (icon) payload.icon = icon;
    try {
      await callService('budget_book', 'add_category', payload);
      closeModal('modal-cat');
    } catch (e) { alert('新增失敗:' + e.message); }
  };

  // Recurring
  $('btn-add-recurring').onclick = openRecurringModal;
  $('rec-type').onchange = () => {
    const book = getActiveBook();
    const type = $('rec-type').value;
    const catSel = $('rec-category');
    catSel.innerHTML = book.categories.filter(c => c.type === type)
      .map(c => `<option value="${c.id}">${c.name}</option>`).join('');
  };
  $('rec-submit').onclick = async () => {
    const data = {
      name: $('rec-name').value.trim(),
      type: $('rec-type').value,
      amount: parseFloat($('rec-amount').value),
      category: $('rec-category').value,
      day_of_month: parseInt($('rec-day').value),
      note: $('rec-note').value
    };
    if (!data.name || !data.amount || !data.day_of_month) { alert('請填寫名稱、金額、每月幾號'); return; }
    try {
      await callService('budget_book', 'add_recurring', data);
      closeModal('modal-recurring');
    } catch (e) { alert('新增失敗:' + e.message); }
  };
  $('btn-run-recurring').onclick = async () => {
    try {
      await callService('budget_book', 'run_recurring');
      alert('已執行檢查');
    } catch (e) { alert('執行失敗:' + e.message); }
  };

  // Book management
  $('btn-new-book').onclick = openBookModal;
  $('book-submit').onclick = async () => {
    const name = $('book-name').value.trim();
    const currency = $('book-currency').value.trim() || 'TWD';
    if (!name) { alert('請輸入名稱'); return; }
    try {
      await callService('budget_book', 'create_book', { name, currency });
      closeModal('modal-book');
    } catch (e) { alert('建立失敗:' + e.message); }
  };

  // Data management
  $('btn-export').onclick = () => {
    const data = getData();
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    const a = document.createElement('a');
    a.href = url;
    a.download = `budget_book_${ts}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  $('btn-import').onclick = () => $('import-file').click();
  $('import-file').addEventListener('change', async (ev) => {
    const file = ev.target.files && ev.target.files[0];
    ev.target.value = '';
    if (!file) return;
    let parsed;
    try {
      const text = await file.text();
      parsed = JSON.parse(text);
    } catch (e) {
      alert('JSON 解析失敗:' + e.message);
      return;
    }
    if (!parsed.books || typeof parsed.books !== 'object') {
      alert('格式錯誤:缺少 books 欄位');
      return;
    }
    const bookCount = Object.keys(parsed.books).length;
    if (!confirm(`即將匯入 ${bookCount} 本記帳本,這會「覆蓋」所有現有資料。確定?\n\n建議先匯出備份。`)) return;
    try {
      await callService('budget_book', 'replace_data', { data: parsed });
      alert('匯入完成');
    } catch (e) { alert('匯入失敗:' + e.message); }
  });
  $('btn-load-sample').onclick = async () => {
    if (!confirm('將覆蓋現有所有資料為範例資料(兩本記帳本)。確定?')) return;
    try { await callService('budget_book', 'load_sample'); }
    catch (e) { alert('載入失敗:' + e.message); }
  };
  $('btn-clear').onclick = async () => {
    if (!confirm('清空「目前」記帳本的所有交易、預算、固定支出。確定?')) return;
    if (!confirm('再次確認 — 不可復原!')) return;
    try { await callService('budget_book', 'clear_all'); }
    catch (e) { alert('清除失敗:' + e.message); }
  };
}

// ============================================================
// Bootstrap
// ============================================================

(async () => {
  log('Bootstrap start');
  try { bindEvents(); } catch (e) { log('bindEvents error:', e.message); }
  const ok = await connectHA();
  if (ok) {
    $('loading').style.display = 'none';
    $('main').style.display = 'block';
    render();
  }
})().catch(e => {
  log('Bootstrap fatal:', e.message);
  showError('啟動失敗:' + e.message);
});
