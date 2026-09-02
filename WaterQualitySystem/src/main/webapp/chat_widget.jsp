<%@ page pageEncoding="UTF-8" %>
<%--
  聊天智能体左侧边栏（全局片段）
  被 template_header.jsp 静态 include。
  支持：左侧收起/展开、会话历史持久化、新对话、流式对话、图表/下载渲染。
  纯前端：fetch 调用 FastAPI 聊天服务（默认 http://127.0.0.1:8001/chat）。
--%>
<!-- ==================== 聊天左侧边栏 ==================== -->
<style>
  /* 收起把手（固定在左边缘，中间） */
  #chat-sidebar-handle {
    position: fixed;
    left: 0; top: 50%;
    transform: translateY(-50%);
    z-index: 1060;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    background: linear-gradient(135deg, var(--c-water), var(--c-teal-500));
    color: #fff;
    border: none;
    border-radius: 0 12px 12px 0;
    padding: 10px 6px;
    cursor: pointer;
    box-shadow: 0 6px 18px rgba(14,165,233,0.4);
    font-size: 0.68rem;
    transition: transform var(--duration) var(--ease-out);
  }
  #chat-sidebar-handle:hover { transform: translateY(-50%) translateX(2px); }
  #chat-sidebar-handle i { font-size: 1.15rem; }
  #chat-sidebar-handle .cs-label { writing-mode: vertical-rl; letter-spacing: 2px; }

  /* 左侧边栏主体 */
  #chat-sidebar {
    position: fixed;
    left: 0; top: 0; bottom: 0;
    width: 372px;
    max-width: calc(100vw - 24px);
    background: var(--surface);
    border-right: 1px solid var(--border);
    box-shadow: var(--shadow-xl);
    z-index: 1061;
    display: flex;
    flex-direction: column;
    transform: translateX(-100%);
    transition: transform 240ms var(--ease-out);
  }
  #chat-sidebar.open { transform: translateX(0); }

  /* 标题栏 */
  #chat-sidebar .chat-header {
    background: linear-gradient(135deg, var(--c-ocean), var(--c-teal-700));
    color: #fff;
    padding: 0.85rem 1rem;
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  #chat-sidebar .ch-avatar {
    width: 36px; height: 36px; border-radius: 50%;
    background: rgba(255,255,255,0.2);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem;
  }
  #chat-sidebar .ch-title { font-weight: 700; font-size: 0.95rem; line-height: 1.2; }
  #chat-sidebar .ch-sub { font-size: 0.72rem; opacity: 0.85; }
  #chat-sidebar .ch-header-actions { margin-left: auto; display: flex; gap: 0.3rem; }
  .ch-icon-btn {
    background: rgba(255,255,255,0.15);
    border: none; color: #fff;
    width: 30px; height: 30px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; font-size: 1rem; opacity: 0.9;
    transition: background var(--duration) var(--ease-out);
  }
  .ch-icon-btn:hover { background: rgba(255,255,255,0.3); opacity: 1; }

  /* 消息区 */
  #chat-sidebar .chat-body {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
    background: var(--surface-alt);
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
  }
  .chat-msg { display: flex; gap: 0.5rem; max-width: 92%; }
  .chat-msg.user { align-self: flex-end; flex-direction: row-reverse; }
  .chat-msg .bubble {
    padding: 0.55rem 0.85rem;
    border-radius: var(--r-md);
    font-size: 0.88rem;
    line-height: 1.55;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .chat-msg.user .bubble { background: var(--c-water); color: #fff; border-bottom-right-radius: 4px; }
  .chat-msg.ai .bubble { background: #fff; color: var(--text); border: 1px solid var(--border); border-bottom-left-radius: 4px; }
  .chat-msg .avatar {
    width: 30px; height: 30px; border-radius: 50%;
    flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.9rem;
  }
  .chat-msg.user .avatar { background: var(--c-foam); color: var(--c-ocean); }
  .chat-msg.ai .avatar { background: var(--c-teal-100); color: var(--c-teal-700); }

  /* 正在输入指示 */
  .chat-typing { display: flex; gap: 4px; padding: 0.6rem 0.85rem; }
  .chat-typing span {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--text-muted);
    animation: typingBounce 1.2s infinite ease-in-out;
  }
  .chat-typing span:nth-child(2) { animation-delay: 0.15s; }
  .chat-typing span:nth-child(3) { animation-delay: 0.3s; }
  @keyframes typingBounce {
    0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
    30% { transform: translateY(-6px); opacity: 1; }
  }

  /* 快捷问题 */
  #chat-sidebar .chat-quick {
    display: flex; flex-wrap: wrap; gap: 0.4rem;
    padding: 0 1rem 0.6rem; background: var(--surface-alt);
  }
  #chat-sidebar .chat-quick button {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: var(--r-full);
    padding: 0.3rem 0.7rem;
    font-size: 0.76rem;
    color: var(--c-ocean);
    cursor: pointer;
    transition: all 120ms var(--ease-out);
    font-family: var(--font-body);
  }
  #chat-sidebar .chat-quick button:hover { background: var(--c-foam); border-color: var(--c-sky); }

  /* 输入区 */
  #chat-sidebar .chat-input-area {
    border-top: 1px solid var(--border);
    padding: 0.6rem;
    background: #fff;
    display: flex;
    gap: 0.5rem;
    align-items: flex-end;
  }
  #chat-sidebar .chat-input-area textarea {
    flex: 1;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: 0.55rem 0.75rem;
    font-size: 0.88rem;
    font-family: var(--font-body);
    resize: none;
    max-height: 100px;
    line-height: 1.5;
  }
  #chat-sidebar .chat-input-area textarea:focus {
    outline: none;
    border-color: var(--c-sky);
    box-shadow: 0 0 0 3px rgba(14,165,233,0.1);
  }
  #chat-sidebar .chat-send {
    background: var(--c-water); color: #fff; border: none;
    border-radius: var(--r-md); width: 42px; height: 42px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; cursor: pointer;
    flex-shrink: 0;
  }
  #chat-sidebar .chat-send:hover { background: var(--c-ocean); }
  #chat-sidebar .chat-send:disabled { background: var(--text-muted); cursor: not-allowed; }

  /* 历史会话列表覆盖层 */
  #chat-session-panel {
    position: absolute;
    inset: 0;
    background: var(--surface);
    display: none;
    flex-direction: column;
    z-index: 10;
  }
  #chat-session-panel.open { display: flex; }
  .cs-panel-header {
    padding: 0.9rem 1rem;
    background: linear-gradient(135deg, var(--c-ocean), var(--c-teal-700));
    color: #fff;
    display: flex; align-items: center; justify-content: space-between;
    font-weight: 700;
  }
  .chat-sessions { flex: 1; overflow-y: auto; padding: 0.6rem; display: flex; flex-direction: column; gap: 0.5rem; }
  .cs-item {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: 0.6rem 0.75rem;
    cursor: pointer;
    transition: border-color var(--duration) var(--ease-out), background var(--duration) var(--ease-out);
  }
  .cs-item:hover { background: var(--c-foam); border-color: var(--c-sky); }
  .cs-item.active { border-color: var(--c-water); background: var(--c-foam); }
  .cs-item .cs-title { font-size: 0.85rem; font-weight: 600; color: var(--text); margin-bottom: 3px; word-break: break-all; }
  .cs-item .cs-meta { font-size: 0.72rem; color: var(--text-muted); }
  .cs-empty { text-align: center; color: var(--text-muted); padding: 1.5rem; font-size: 0.85rem; }

  /* 滚动条 */
  #chat-sidebar .chat-body::-webkit-scrollbar,
  .chat-sessions::-webkit-scrollbar { width: 6px; }
  #chat-sidebar .chat-body::-webkit-scrollbar-thumb,
  .chat-sessions::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  @media (max-width: 480px) {
    #chat-sidebar { width: 100%; max-width: 100%; }
    #chat-sidebar-handle { display: none; }
  }
</style>

<!-- 左侧边栏 -->
<aside id="chat-sidebar">
  <div class="chat-header">
    <div class="ch-avatar"><i class="bi bi-droplet-half"></i></div>
    <div>
      <div class="ch-title">水质智能助手</div>
      <div class="ch-sub">可查库 · 做预测 · 查标准 · 会话历史</div>
    </div>
    <div class="ch-header-actions">
      <button class="ch-icon-btn" id="chat-new" title="新对话"><i class="bi bi-plus-lg"></i></button>
      <button class="ch-icon-btn" id="chat-history" title="历史会话"><i class="bi bi-clock-history"></i></button>
      <button class="ch-icon-btn" id="chat-close" title="收起"><i class="bi bi-arrow-bar-left"></i></button>
    </div>
  </div>

  <div class="chat-body" id="chat-body"></div>

  <div class="chat-quick">
    <button onclick="quickAsk('最近有哪些不合格的水样？')">最近不合格水样</button>
    <button onclick="quickAsk('对照饮用水标准检查最近的检测记录')">标准对照</button>
    <button onclick="quickAsk('最近30天水质趋势怎么样')">水质趋势</button>
    <button onclick="quickAsk('给我看下检测结果分布图')">结果分布图</button>
    <button onclick="quickAsk('有哪些未处理的预警？')">未处理预警</button>
  </div>

  <div class="chat-input-area">
    <textarea id="chat-input" rows="1" placeholder="输入问题，Enter 发送，Shift+Enter 换行"
              onkeydown="onChatKey(event)" oninput="autoGrow(this)"></textarea>
    <button class="chat-send" id="chat-send" onclick="sendChat()" title="发送">
      <i class="bi bi-send-fill"></i>
    </button>
  </div>

  <!-- 历史会话列表（覆盖层） -->
  <div id="chat-session-panel">
    <div class="cs-panel-header">
      <span><i class="bi bi-clock-history"></i> 历史会话</span>
      <button class="ch-icon-btn" id="chat-session-close" title="关闭">&times;</button>
    </div>
    <div id="chat-sessions" class="chat-sessions"></div>
  </div>
</aside>

<!-- 收起把手 -->
<button id="chat-sidebar-handle" onclick="toggleSidebar(true)" title="展开水质助手">
  <i class="bi bi-chat-dots-fill"></i>
  <span class="cs-label">水质助手</span>
</button>

<script>
  // ==================== 配置 ====================
  const CHAT_BASE = window.location.hostname === 'localhost'
      ? 'http://127.0.0.1:8001' : 'http://' + window.location.hostname + ':8001';

  // ==================== 状态 ====================
  let chatHistory = [];      // [{role, content}]
  let chatSending = false;
  let currentSessionId = null;
  let sessionList = [];
  const chatClientId = (function () {
    let id = localStorage.getItem('wq_chat_client');
    if (!id) {
      id = 'c_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem('wq_chat_client', id);
    }
    return id;
  })();
  const GREETING = '你好！我是水质安全智能助手。可以问我：\n· 最近有哪些不合格的水样\n· 对照标准检查某些记录\n· 最近水质趋势怎么样\n· 给我看下检测结果分布图';

  // ==================== UI 控制 ====================
  function toggleSidebar(open) {
    const sb = document.getElementById('chat-sidebar');
    if (typeof open === 'boolean') sb.classList.toggle('open', open);
    else sb.classList.toggle('open');
    if (sb.classList.contains('open')) {
      setTimeout(() => document.getElementById('chat-input').focus(), 120);
    }
  }

  function autoGrow(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 100) + 'px';
  }

  function onChatKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChat();
    }
  }

  function quickAsk(q) {
    document.getElementById('chat-input').value = q;
    sendChat();
  }

  // ==================== 消息渲染 ====================
  function appendUser(text) {
    const body = document.getElementById('chat-body');
    const div = document.createElement('div');
    div.className = 'chat-msg user';
    div.innerHTML = '<div class="avatar"><i class="bi bi-person-fill"></i></div>'
                  + '<div class="bubble"></div>';
    div.querySelector('.bubble').textContent = text;
    body.appendChild(div);
    scrollChatBottom();
  }

  function appendAIBubble() {
    const body = document.getElementById('chat-body');
    const div = document.createElement('div');
    div.className = 'chat-msg ai';
    div.innerHTML = '<div class="avatar"><i class="bi bi-robot"></i></div>'
                  + '<div class="bubble"></div>';
    body.appendChild(div);
    scrollChatBottom();
    return div.querySelector('.bubble');
  }

  function showTyping() {
    const body = document.getElementById('chat-body');
    const div = document.createElement('div');
    div.className = 'chat-msg ai';
    div.id = 'chat-typing-msg';
    div.innerHTML = '<div class="avatar"><i class="bi bi-robot"></i></div>'
                  + '<div class="chat-typing"><span></span><span></span><span></span></div>';
    body.appendChild(div);
    scrollChatBottom();
  }
  function removeTyping() {
    const el = document.getElementById('chat-typing-msg');
    if (el) el.remove();
  }

  function scrollChatBottom() {
    const body = document.getElementById('chat-body');
    body.scrollTop = body.scrollHeight;
  }

  function renderChatBody() {
    const body = document.getElementById('chat-body');
    body.innerHTML = '';
    if (!chatHistory.length) {
      // 欢迎语
      const div = document.createElement('div');
      div.className = 'chat-msg ai';
      div.innerHTML = '<div class="avatar"><i class="bi bi-robot"></i></div>'
                    + '<div class="bubble"></div>';
      div.querySelector('.bubble').textContent = GREETING;
      body.appendChild(div);
    } else {
      chatHistory.forEach(function (m) {
        if (m.role === 'user') {
          appendUser(m.content);
        } else {
          const bubble = appendAIBubble();
          bubble.innerHTML = renderRich(m.content);
        }
      });
    }
    scrollChatBottom();
  }

  // ==================== 富文本渲染（图片 / 下载链接） ====================
  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // URL 白名单：只允许 http/https 外链与本站 /static/ 资源，其余一律拒绝，
  // 防止模型/文本注入 javascript: 或破坏 HTML 属性。
  function absUrl(url) {
    url = (url || '').trim();
    if (/^https?:\/\//i.test(url)) return url;
    if (/^\/static\//i.test(url)) return CHAT_BASE + url;
    return '#';
  }

  function renderRich(text) {
    let s = escapeHtml(text);
    const ph = [];
    function stash(html) {
      const token = '\u0001P' + ph.length + '\u0001';
      ph.push(html);
      return token;
    }
    // markdown 图片 ![alt](url)
    s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, function (m, alt, url) {
      return stash('<img src="' + absUrl(url) + '" alt="' + alt + '" style="max-width:100%;border-radius:8px;margin:6px 0;display:block;">');
    });
    // markdown 链接 [label](url)
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (m, label, url) {
      return stash('<a href="' + absUrl(url) + '" target="_blank" rel="noopener" style="color:var(--c-water)">' + label + '</a>');
    });
    // 单独成行的图片 URL（http 或 /static）——用占位符避免二次命中已生成的 <img>
    s = s.replace(/(https?:\/\/\S+?\.(?:png|jpe?g|gif|webp))/gim, function (m, url) {
      return stash('<img src="' + url + '" style="max-width:100%;border-radius:8px;margin:6px 0;display:block;">');
    });
    s = s.replace(/(\/static\/[^\s]+?\.(?:png|jpe?g|gif|webp))/gim, function (m, url) {
      return stash('<img src="' + CHAT_BASE + url + '" style="max-width:100%;border-radius:8px;margin:6px 0;display:block;">');
    });
    // 单独成行的下载链接
    s = s.replace(/(https?:\/\/\S+?\.(?:csv|xlsx?|pdf|zip))/gim, function (m, url) {
      return stash('<a href="' + url + '" target="_blank" rel="noopener" style="color:var(--c-water)">⬇ 下载文件</a>');
    });
    s = s.replace(/(\/static\/[^\s]+?\.(?:csv|xlsx?|pdf|zip))/gim, function (m, url) {
      return stash('<a href="' + CHAT_BASE + url + '" target="_blank" rel="noopener" style="color:var(--c-water)">⬇ 下载文件</a>');
    });
    // 还原占位符
    s = s.replace(/\u0001P(\d+)\u0001/g, function (m, i) {
      return ph[+i] || '';
    });
    return s;
  }

  // ==================== 会话历史 ====================
  async function loadOrCreateSession() {
    try {
      const r = await fetch(CHAT_BASE + '/sessions?client_id=' + encodeURIComponent(chatClientId));
      const j = await r.json();
      sessionList = j.sessions || [];
      if (sessionList.length) {
        await loadSession(sessionList[0].id);
      } else {
        await newChat();
      }
    } catch (e) {
      // 后端不可用时也能本地聊（不持久化）
      chatHistory = [];
      renderChatBody();
    }
  }

  async function newChat() {
    try {
      const r = await fetch(CHAT_BASE + '/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_id: chatClientId, title: '新对话' })
      });
      const j = await r.json();
      currentSessionId = j.session_id || null;
    } catch (e) {
      currentSessionId = null;
    }
    chatHistory = [];
    renderChatBody();
    // 关掉历史面板，回到聊天
    document.getElementById('chat-session-panel').classList.remove('open');
  }

  async function loadSession(sid) {
    try {
      const r = await fetch(CHAT_BASE + '/sessions/' + sid + '/messages?client_id=' + encodeURIComponent(chatClientId));
      const j = await r.json();
      currentSessionId = sid;
      chatHistory = (j.messages || []).map(function (m) {
        return { role: m.role, content: m.content };
      });
      renderChatBody();
      document.getElementById('chat-session-panel').classList.remove('open');
    } catch (e) {
      alert('加载会话失败：' + e.message);
    }
  }

  async function refreshSessions() {
    try {
      const r = await fetch(CHAT_BASE + '/sessions?client_id=' + encodeURIComponent(chatClientId));
      const j = await r.json();
      sessionList = j.sessions || [];
      renderSessionList();
    } catch (e) {
      sessionList = [];
      renderSessionList();
    }
  }

  function renderSessionList() {
    const box = document.getElementById('chat-sessions');
    box.innerHTML = '';
    if (!sessionList.length) {
      box.innerHTML = '<div class="cs-empty">还没有历史会话，点击左上角「+」新建一个。</div>';
      return;
    }
    sessionList.forEach(function (s) {
      const div = document.createElement('div');
      div.className = 'cs-item' + (s.id === currentSessionId ? ' active' : '');
      const title = s.title || '新对话';
      const meta = (s.msg_count || 0) + ' 条消息' + (s.updated_at ? ' · ' + s.updated_at : '');
      const preview = s.last_preview ? '<div class="cs-meta">' + escapeHtml(s.last_preview) + '</div>' : '';
      div.innerHTML = '<div class="cs-title">' + escapeHtml(title) + '</div>'
                    + '<div class="cs-meta">' + meta + '</div>' + preview;
      div.onclick = function () { loadSession(s.id); };
      box.appendChild(div);
    });
  }

  function openHistory() {
    const panel = document.getElementById('chat-session-panel');
    panel.classList.add('open');
    refreshSessions();
  }

  // ==================== 发送 + 流式接收 ====================
  async function sendChat() {
    if (chatSending) return;
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;

    appendUser(text);
    chatHistory.push({ role: 'user', content: text });
    input.value = '';
    input.style.height = 'auto';

    setSending(true);
    showTyping();

    try {
      const resp = await fetch(CHAT_BASE + '/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: text,
          // 只带当前问题之前的最近 10 条（当前 query 单独传，避免重复）
          history: chatHistory.slice(-11, -1),
          session_id: currentSessionId,
          client_id: chatClientId
        })
      });

      if (!resp.ok) throw new Error('HTTP ' + resp.status);

      removeTyping();
      const bubble = appendAIBubble();

      const reader = resp.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let full = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        full += chunk;
        bubble.textContent = full;
        scrollChatBottom();
      }
      bubble.innerHTML = renderRich(full);
      chatHistory.push({ role: 'assistant', content: full });
      // 更新历史列表标题/预览（仅当历史面板开着或标题已更新时刷新一次）
      if (currentSessionId) refreshSessions();
    } catch (err) {
      removeTyping();
      const bubble = appendAIBubble();
      bubble.textContent = '连接失败：' + err.message
          + '\n\n请确认聊天服务已启动（python chat_main.py，端口 8001）。';
      bubble.style.color = 'var(--danger)';
    } finally {
      setSending(false);
    }
  }

  function setSending(v) {
    chatSending = v;
    document.getElementById('chat-send').disabled = v;
  }

  // ==================== 事件绑定 + 初始化 ====================
  (function bind() {
    document.getElementById('chat-new').addEventListener('click', newChat);
    document.getElementById('chat-history').addEventListener('click', openHistory);
    document.getElementById('chat-close').addEventListener('click', function () { toggleSidebar(false); });
    document.getElementById('chat-session-close').addEventListener('click', function () {
      document.getElementById('chat-session-panel').classList.remove('open');
    });
    loadOrCreateSession();
  })();
</script>
<!-- ==================== /聊天左侧边栏 ==================== -->
