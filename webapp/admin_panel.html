<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Панель администратора</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root {
  --bg:#0f1117; --surface:#1a1d27; --border:#2a2d3a;
  --text:#e8eaf0; --muted:#7a7e91; --accent:#4f7ef8;
  --green:#3ecf75; --red:#e05252; --yellow:#e8b94a; --r:10px;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;min-height:100vh}
.nav{display:flex;border-bottom:1px solid var(--border);overflow-x:auto}
.nav::-webkit-scrollbar{display:none}
.nav-item{flex-shrink:0;padding:12px 14px;font-size:12px;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}
.nav-item.active{color:var(--accent);border-bottom-color:var(--accent)}
.section{display:none;padding:16px}
.section.active{display:block}
.section-title{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:14px}
/* Auth */
#auth-screen{min-height:100vh;display:flex;flex-direction:column;justify-content:center;padding:32px 20px}
#auth-screen h1{font-size:20px;font-weight:600;margin-bottom:8px}
#auth-screen p{font-size:13px;color:var(--muted);margin-bottom:28px}
.field{margin-bottom:14px}
.field label{font-size:12px;color:var(--muted);display:block;margin-bottom:6px}
.field input{width:100%;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:11px 12px;color:var(--text);font-size:14px;outline:none}
.field input:focus{border-color:var(--accent)}
.btn{width:100%;padding:12px;background:var(--accent);border:none;border-radius:var(--r);color:#fff;font-size:14px;font-weight:500;cursor:pointer}
.btn.sm{width:auto;padding:7px 14px;font-size:13px}
.btn.secondary{background:none;border:1px solid var(--border);color:var(--muted);margin-top:10px}
.btn.danger{background:var(--red)}
.err{color:var(--red);font-size:13px;margin-bottom:12px;display:none}
/* Cards */
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:14px;margin-bottom:10px}
.card-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.card .label{font-size:11px;color:var(--muted);margin-bottom:4px}
.card .val{font-size:15px;font-weight:600}
.card .sub{font-size:12px;color:var(--muted)}
/* Balance */
.balance-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px}
.balance-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:16px;text-align:center}
.balance-card .big{font-size:26px;font-weight:700;color:var(--accent)}
.balance-card .lbl{font-size:12px;color:var(--muted);margin-top:4px}
.withdraw-form{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:16px;margin-bottom:14px}
.withdraw-form h3{font-size:14px;font-weight:600;margin-bottom:12px}
textarea{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:10px 12px;color:var(--text);font-size:13px;outline:none;resize:vertical;min-height:70px;font-family:inherit}
textarea:focus{border-color:var(--accent)}
input.sm-input{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:9px 12px;color:var(--text);font-size:13px;outline:none;width:100%}
input.sm-input:focus{border-color:var(--accent)}
.pill{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px}
.pill.pending{background:#2a2714;color:var(--yellow)}
.pill.approved{background:#1e3a24;color:var(--green)}
.pill.rejected{background:#3a1e1e;color:var(--red)}
/* Dialogs */
.dlg-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:13px;margin-bottom:10px;cursor:pointer}
.dlg-card:active{background:#22263a}
.dlg-meta{display:flex;justify-content:space-between;align-items:center}
.dlg-id{font-size:14px;font-weight:500}
.dlg-badge{background:var(--red);color:#fff;border-radius:20px;padding:1px 8px;font-size:11px}
.dlg-sub{font-size:12px;color:var(--muted);margin-top:4px}
/* Chat */
#chat-view{display:none;flex-direction:column;height:100vh}
.chat-header{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid var(--border);flex-shrink:0}
.chat-header button{background:none;border:none;color:var(--accent);font-size:15px;cursor:pointer}
.chat-header span{font-size:15px;font-weight:500}
.messages{flex:1;overflow-y:auto;padding:12px 16px;display:flex;flex-direction:column;gap:8px}
.msg{max-width:78%}
.msg.user{align-self:flex-start}
.msg.admin{align-self:flex-end}
.msg-label{font-size:10px;color:var(--muted);margin-bottom:3px;padding:0 4px}
.msg.admin .msg-label{text-align:right}
.msg-bubble{padding:9px 12px;border-radius:14px;font-size:14px;line-height:1.5;word-break:break-word}
.msg.user .msg-bubble{background:var(--surface);border:1px solid var(--border)}
.msg.admin .msg-bubble{background:var(--accent);color:#fff}
.msg-time{font-size:10px;color:var(--muted);margin-top:3px;padding:0 4px}
.msg.admin .msg-time{text-align:right}
.msg-media{border-radius:10px;max-width:220px;margin-bottom:4px;display:block}
/* Channel */
.post-item{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:12px;margin-bottom:10px}
.post-item .post-text{font-size:13px;margin-bottom:8px}
.post-item .post-meta{display:flex;justify-content:space-between;font-size:11px;color:var(--muted)}
.del-btn{background:none;border:none;color:var(--red);font-size:12px;cursor:pointer;padding:0}
.divider{border:none;border-top:1px solid var(--border);margin:16px 0}
.empty{color:var(--muted);font-size:13px;padding:20px 0;text-align:center}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1e3a24;color:var(--green);padding:10px 20px;border-radius:var(--r);font-size:13px;display:none;z-index:999}
.loading{text-align:center;padding:40px;color:var(--muted);font-size:14px}
</style>
</head>
<body>

<!-- Auth / Loading -->
<div id="auth-screen" style="display:none">
  <h1>Панель администратора</h1>
  <p>Войдите через Telegram или используйте пароль.</p>
  <div class="err" id="auth-err">Нет доступа или ошибка входа</div>
  <div class="field"><label>Псевдоним</label><input id="l-user" type="text" autocomplete="username"></div>
  <div class="field"><label>Пароль</label><input id="l-pass" type="password" autocomplete="current-password"></div>
  <button class="btn" onclick="loginWithPassword()">Войти по паролю</button>
</div>

<div id="loading-screen" style="min-height:100vh;display:flex;align-items:center;justify-content:center">
  <div class="loading">Загрузка...</div>
</div>

<!-- Main app -->
<div id="app" style="display:none">
  <nav class="nav">
    <div class="nav-item active" id="n-dialogs"  onclick="showTab('dialogs')">Диалоги</div>
    <div class="nav-item"        id="n-balance"  onclick="showTab('balance')">Баланс</div>
    <div class="nav-item"        id="n-channel"  onclick="showTab('channel')">Канал</div>
    <div class="nav-item"        id="n-profile"  onclick="showTab('profile')">Профиль</div>
  </nav>

  <!-- Dialogs -->
  <div class="section active" id="tab-dialogs">
    <div class="section-title">Активные диалоги</div>
    <div id="dlg-list"></div>
  </div>

  <!-- Balance -->
  <div class="section" id="tab-balance">
    <div class="section-title">Мой баланс</div>
    <div class="balance-grid">
      <div class="balance-card">
        <div class="big" id="bal-msg">—</div>
        <div class="lbl">Сообщений</div>
      </div>
      <div class="balance-card">
        <div class="big" id="bal-rub">—</div>
        <div class="lbl">Рублей</div>
      </div>
    </div>
    <div class="card" style="margin-bottom:14px">
      <div class="label">Ставка</div>
      <div class="val" id="bal-rate">—</div>
      <div class="sub">руб. за одно сообщение</div>
    </div>

    <div class="withdraw-form">
      <h3>Заявка на вывод</h3>
      <div class="field">
        <label>Сумма (руб.)</label>
        <input class="sm-input" id="w-amount" type="number" min="1" step="0.01" placeholder="Введите сумму">
      </div>
      <div class="field">
        <label>Реквизиты (карта / кошелёк / телефон)</label>
        <textarea id="w-details" rows="3" placeholder="Например: Тинькофф 4278 1234 5678 9000 / Иван И."></textarea>
      </div>
      <button class="btn" onclick="submitWithdrawal()">Отправить заявку</button>
    </div>

    <div class="section-title">История выводов</div>
    <div id="withdrawals-list"></div>
  </div>

  <!-- Channel -->
  <div class="section" id="tab-channel">
    <div class="section-title">Управление каналом</div>
    <div class="field"><label>Название</label><input class="sm-input" id="ch-title" type="text"></div>
    <div class="field"><label>Описание</label><textarea id="ch-desc" rows="2"></textarea></div>
    <button class="btn sm" style="margin-bottom:16px" onclick="saveChannel()">Сохранить</button>
    <hr class="divider">
    <div class="section-title">Новый пост</div>
    <div class="field"><label>Текст</label><textarea id="post-text" rows="4"></textarea></div>
    <button class="btn sm" onclick="publishPost()">Опубликовать</button>
    <hr class="divider">
    <div class="section-title">Мои посты</div>
    <div id="posts-list"></div>
  </div>

  <!-- Profile -->
  <div class="section" id="tab-profile">
    <div class="card" id="profile-card"></div>
    <button class="btn secondary" style="margin-top:12px" onclick="logout()">Выйти</button>
  </div>
</div>

<!-- Chat view -->
<div id="chat-view">
  <div class="chat-header">
    <button onclick="closeChat()">&#8592;</button>
    <span id="chat-title">Диалог</span>
  </div>
  <div class="messages" id="messages"></div>
</div>

<div class="toast" id="toast"></div>

<script>
const tg  = window.Telegram?.WebApp;
tg?.expand();
tg?.ready();

const API       = location.origin;
let token       = sessionStorage.getItem('adm_token');
let currentAdminId  = null;
let currentDialogId = null;
let pollInterval    = null;

// ── Авто-вход через Telegram initData ───────────────────────────────────────
async function autoLogin() {
  const initData = tg?.initData;
  if (initData) {
    try {
      const res = await fetch(`${API}/auth/tg`, {
        method:  'POST',
        headers: {'Content-Type':'application/json'},
        body:    JSON.stringify({ init_data: initData }),
      });
      if (res.ok) {
        const d = await res.json();
        onLoginSuccess(d);
        return;
      }
    } catch(e) {}
  }
  // Если initData нет или не прошло — показываем форму входа
  document.getElementById('loading-screen').style.display = 'none';
  document.getElementById('auth-screen').style.display = '';
}

async function loginWithPassword() {
  const u = document.getElementById('l-user').value.trim();
  const p = document.getElementById('l-pass').value.trim();
  const res = await fetch(`${API}/auth/login`, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ pseudonym: u, password: p }),
  });
  if (!res.ok) { document.getElementById('auth-err').style.display = 'block'; return; }
  onLoginSuccess(await res.json());
}

function onLoginSuccess(d) {
  token          = d.token;
  currentAdminId = d.user.id;
  sessionStorage.setItem('adm_token', token);
  document.getElementById('auth-screen').style.display   = 'none';
  document.getElementById('loading-screen').style.display = 'none';
  document.getElementById('app').style.display            = '';
  loadAll();
}

function logout() {
  fetch(`${API}/auth/logout`, { method: 'POST', headers: auth() }).catch(()=>{});
  sessionStorage.removeItem('adm_token');
  token = null;
  document.getElementById('app').style.display  = 'none';
  document.getElementById('auth-screen').style.display = '';
}

function auth() {
  return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };
}

// Если уже есть токен — пробуем сразу
if (token) {
  document.getElementById('loading-screen').style.display = 'none';
  document.getElementById('app').style.display = '';
  // Получаем данные профиля чтобы узнать id
  fetch(`${API}/admin/me`, { headers: auth() }).then(r => {
    if (!r.ok) { token = null; sessionStorage.removeItem('adm_token'); autoLogin(); return; }
    return r.json();
  }).then(me => {
    if (!me) return;
    currentAdminId = me.id;
    loadAll();
  });
} else {
  autoLogin();
}

// ── Tabs ─────────────────────────────────────────────────────────────────────
function showTab(tab) {
  ['dialogs','balance','channel','profile'].forEach(t => {
    document.getElementById('tab-'+t).classList.toggle('active', t===tab);
    document.getElementById('n-'+t).classList.toggle('active', t===tab);
  });
  if (tab === 'balance') loadBalance();
  if (tab === 'channel') loadChannel();
  if (tab === 'profile') loadProfile();
}

function loadAll() { loadDialogs(); }

// ── Dialogs ──────────────────────────────────────────────────────────────────
async function loadDialogs() {
  const res  = await fetch(`${API}/admin/dialogs`, { headers: auth() });
  if (!res.ok) { if (res.status===401) { logout(); } return; }
  const dlgs = await res.json();
  const el   = document.getElementById('dlg-list');
  if (!dlgs.length) {
    el.innerHTML = '<div class="empty">Нет активных диалогов</div>';
    return;
  }
  el.innerHTML = dlgs.map(d => `
    <div class="dlg-card" onclick="openChat(${d.id})">
      <div class="dlg-meta">
        <span class="dlg-id">Диалог #${d.id}</span>
        ${d.unread > 0 ? `<span class="dlg-badge">${d.unread} новых</span>` : ''}
      </div>
      <div class="dlg-sub">${d.is_anonymous ? 'Анонимный' : 'С профилем'} · ${fmtDate(d.created_at)}</div>
    </div>
  `).join('');
}

async function openChat(dialogId) {
  currentDialogId = dialogId;
  document.getElementById('app').style.display = 'none';
  document.getElementById('chat-view').style.display = 'flex';
  document.getElementById('chat-title').textContent = `Диалог #${dialogId}`;
  await loadMessages();
  pollInterval = setInterval(loadMessages, 3500);
}

function closeChat() {
  clearInterval(pollInterval);
  document.getElementById('chat-view').style.display = 'none';
  document.getElementById('app').style.display = '';
  loadDialogs();
}

async function loadMessages() {
  const res  = await fetch(`${API}/admin/dialogs/${currentDialogId}/messages`, { headers: auth() });
  if (!res.ok) return;
  const msgs = await res.json();
  const el   = document.getElementById('messages');
  if (!msgs.length) {
    el.innerHTML = '<div class="empty" style="margin-top:40px">Сообщений нет</div>';
    return;
  }
  el.innerHTML = msgs.map(m => {
    const side = m.sender_type;
    const time = new Date(m.created_at).toLocaleTimeString('ru',{hour:'2-digit',minute:'2-digit'});
    let body = '';
    if (m.media_url && m.media_type==='photo') {
      body += `<img class="msg-media" src="${m.media_url}" alt="">`;
    }
    if (m.content) body += `<div class="msg-bubble">${esc(m.content)}</div>`;
    if (!body)     body  = `<div class="msg-bubble" style="opacity:.6;font-style:italic">[${m.media_type||'файл'}]</div>`;
    return `
      <div class="msg ${side}">
        <div class="msg-label">${side==='user'?'Пользователь':'Вы'}</div>
        ${body}
        <div class="msg-time">${time}</div>
      </div>`;
  }).join('');
  el.scrollTop = el.scrollHeight;
}

// ── Balance ───────────────────────────────────────────────────────────────────
async function loadBalance() {
  const [meRes, balRes, wRes] = await Promise.all([
    fetch(`${API}/admin/me`,          { headers: auth() }),
    fetch(`${API}/admin/balance`,     { headers: auth() }),
    fetch(`${API}/admin/withdrawals`, { headers: auth() }),
  ]);
  if (!meRes.ok || !balRes.ok) return;
  const me  = await meRes.json();
  const bal = await balRes.json();

  document.getElementById('bal-msg').textContent  = bal.balance_messages.toLocaleString();
  document.getElementById('bal-rub').textContent  = bal.balance_rub.toFixed(2) + ' ₽';
  document.getElementById('bal-rate').textContent = bal.message_rate.toFixed(2);

  if (wRes.ok) {
    const ws = await wRes.json();
    const el = document.getElementById('withdrawals-list');
    el.innerHTML = ws.length ? ws.map(w => `
      <div class="card">
        <div class="card-row">
          <span style="font-size:14px;font-weight:500">${w.amount_rub.toFixed(2)} ₽</span>
          <span class="pill ${w.status}">${{pending:'Ожидание',approved:'Одобрено',rejected:'Отказ'}[w.status]}</span>
        </div>
        <div class="sub">${esc(w.details)}</div>
        ${w.comment ? `<div class="sub" style="color:var(--red);margin-top:4px">${esc(w.comment)}</div>` : ''}
        <div class="sub" style="margin-top:6px">${fmtDate(w.created_at)}</div>
      </div>
    `).join('') : '<div class="empty">Заявок нет</div>';
  }
}

async function submitWithdrawal() {
  const amount  = parseFloat(document.getElementById('w-amount').value);
  const details = document.getElementById('w-details').value.trim();
  if (!amount || amount <= 0) { toast('Введите корректную сумму'); return; }
  if (!details) { toast('Введите реквизиты'); return; }
  const res = await fetch(`${API}/admin/withdraw`, {
    method: 'POST', headers: auth(),
    body: JSON.stringify({ amount_rub: amount, details }),
  });
  const d = await res.json();
  if (!res.ok) { toast(d.detail || 'Ошибка'); return; }
  toast('Заявка отправлена!');
  document.getElementById('w-amount').value  = '';
  document.getElementById('w-details').value = '';
  loadBalance();
}

// ── Channel ───────────────────────────────────────────────────────────────────
async function loadChannel() {
  const res = await fetch(`${API}/admin/me`, { headers: auth() });
  if (!res.ok) return;
  const me = await res.json();
  document.getElementById('ch-title').value = me.channel_title || '';
  document.getElementById('ch-desc').value  = me.channel_description || '';

  const pr = await fetch(`${API}/channels/${currentAdminId}/posts`);
  const posts = pr.ok ? await pr.json() : [];
  const el = document.getElementById('posts-list');
  el.innerHTML = posts.length ? posts.map(p => `
    <div class="post-item">
      ${p.content ? `<div class="post-text">${esc(p.content)}</div>` : ''}
      <div class="post-meta">
        <span>${fmtDate(p.created_at)} · ${p.views} просм.</span>
        <button class="del-btn" onclick="deletePost(${p.id})">Удалить</button>
      </div>
    </div>
  `).join('') : '<div class="empty">Постов нет</div>';
}

async function saveChannel() {
  const res = await fetch(`${API}/admin/channel`, {
    method: 'PATCH', headers: auth(),
    body: JSON.stringify({
      title:       document.getElementById('ch-title').value.trim(),
      description: document.getElementById('ch-desc').value.trim(),
    }),
  });
  toast(res.ok ? 'Сохранено' : 'Ошибка');
}

async function publishPost() {
  const text = document.getElementById('post-text').value.trim();
  if (!text) return;
  const res = await fetch(`${API}/admin/channel/posts`, {
    method: 'POST', headers: auth(),
    body: JSON.stringify({ content: text }),
  });
  if (res.ok) { toast('Опубликовано!'); document.getElementById('post-text').value = ''; loadChannel(); }
  else toast('Ошибка публикации');
}

async function deletePost(id) {
  if (!confirm('Удалить пост?')) return;
  await fetch(`${API}/admin/channel/posts/${id}`, { method: 'DELETE', headers: auth() });
  loadChannel();
}

// ── Profile ───────────────────────────────────────────────────────────────────
async function loadProfile() {
  const res = await fetch(`${API}/admin/me`, { headers: auth() });
  if (!res.ok) return;
  const me = await res.json();
  document.getElementById('profile-card').innerHTML = `
    <div class="label">Псевдоним</div>
    <div class="val" style="margin-bottom:10px">${esc(me.pseudonym)}</div>
    ${me.age ? `<div class="label">Возраст</div><div class="sub" style="margin-bottom:8px">${esc(me.age)}</div>` : ''}
    ${me.hobbies ? `<div class="label">Увлечения</div><div class="sub" style="margin-bottom:8px">${esc(me.hobbies)}</div>` : ''}
    <div class="label" style="margin-top:8px">Диалогов за неделю</div>
    <div class="sub">${me.weekly_dialogs}</div>
    <div class="label" style="margin-top:8px">Статус</div>
    <div class="sub">${me.is_on_rest ? 'Отдых до '+me.rest_until : (me.is_online ? 'Онлайн' : 'Офлайн')}</div>
  `;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function fmtDate(s) {
  return new Date(s).toLocaleDateString('ru',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
}
function toast(msg, ms=2500) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', ms);
}
</script>
</body>
</html>
