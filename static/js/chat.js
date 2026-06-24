/**
 * 消息模拟器（仅测试）
 * 模拟候选人发消息，验证 HR Agent 自动回复
 */

const jobSelect = document.getElementById('jobSelect');
const platformUid = document.getElementById('platformUid');
const candidateName = document.getElementById('candidateName');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const chatMessages = document.getElementById('chatMessages');
const chatTitle = document.getElementById('chatTitle');
const sessionIdEl = document.getElementById('sessionId');
const sessionStatusEl = document.getElementById('sessionStatus');
const memoryList = document.getElementById('memoryList');

let currentSessionId = null;

async function loadJobs() {
  const res = await fetch('/api/jobs/');
  const jobs = await res.json();
  jobSelect.innerHTML = jobs.length
    ? jobs.map(j => `<option value="${j.id}">${j.title}${j.active ? '' : ' (已停用)'}</option>`).join('')
    : '<option value="">请先在 HR 工作台创建职位</option>';

  if (jobs.length) {
    chatTitle.textContent = `模拟 · ${jobs[0].title}`;
    jobSelect.addEventListener('change', () => {
      chatTitle.textContent = `模拟 · ${jobSelect.selectedOptions[0].text}`;
      resetChat();
    });
  }
}

function resetChat() {
  currentSessionId = null;
  sessionIdEl.textContent = '-';
  sessionStatusEl.textContent = '-';
  chatMessages.innerHTML = '<div class="welcome-msg"><p>🧪 新模拟会话已开始</p></div>';
  memoryList.innerHTML = '<p class="empty-hint">发送消息后显示历史记录</p>';
}

function appendMessage(role, content) {
  const welcome = chatMessages.querySelector('.welcome-msg');
  if (welcome) welcome.remove();

  const div = document.createElement('div');
  div.className = `msg-bubble ${role}`;
  const label = role === 'user' ? '【模拟·候选人】' : '【AI Agent·HR 方】';
  div.textContent = `${label} ${content}`;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function refreshMemory(sessionId) {
  const res = await fetch(`/api/chat/sessions/${sessionId}/messages`);
  const messages = await res.json();
  if (!messages.length) {
    memoryList.innerHTML = '<p class="empty-hint">暂无记录</p>';
    return;
  }
  memoryList.innerHTML = messages.map(m => `
    <div class="memory-item">
      <span class="role">${m.role === 'user' ? '候选人' : 'AI'}:</span>
      ${escapeHtml(m.content.slice(0, 80))}${m.content.length > 80 ? '...' : ''}
    </div>
  `).join('');
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

async function sendMessage() {
  const jobId = parseInt(jobSelect.value);
  const content = messageInput.value.trim();
  if (!jobId || !content) return;

  sendBtn.disabled = true;
  sendBtn.textContent = 'Agent 回复中...';
  appendMessage('user', content);
  messageInput.value = '';

  try {
    const res = await fetch('/api/chat/webhook', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform_uid: platformUid.value.trim() || 'demo_user',
        job_id: jobId,
        message_content: content,
        candidate_name: candidateName.value.trim(),
        platform: 'simulator',
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '请求失败');

    currentSessionId = data.session_id;
    sessionIdEl.textContent = data.session_id;
    sessionStatusEl.textContent = data.status;
    appendMessage('assistant', data.reply);
    await refreshMemory(data.session_id);
  } catch (err) {
    appendMessage('assistant', `❌ 错误: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = '发送';
  }
}

sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

loadJobs();
