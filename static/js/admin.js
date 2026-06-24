/**
 * HR 工作台逻辑
 * 收件箱 + 会话详情 + 职位 Agent 管理
 */

const STATUS_LABELS = {
  WAITING_CANDIDATE: '等待候选人回复',
  WAITING_AI: '等待 AI 处理',
  FOLLOWED_UP_ONCE: '已复聊跟进',
  HUMAN_TAKEOVER: '人工接管中',
};

const jobsList = document.getElementById('jobsList');
const inboxList = document.getElementById('inboxList');
const inboxDetail = document.getElementById('inboxDetail');
const filterJob = document.getElementById('filterJob');
const filterStatus = document.getElementById('filterStatus');
const jobModal = document.getElementById('jobModal');

let currentSessionId = null;
let sessionsCache = [];

// ---------- 导航切换 ----------
document.querySelectorAll('.hr-nav-item').forEach(item => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.hr-nav-item').forEach(i => i.classList.remove('active'));
    document.querySelectorAll('.hr-panel').forEach(p => p.classList.remove('active'));
    item.classList.add('active');
    document.getElementById(`panel-${item.dataset.tab}`).classList.add('active');
    if (item.dataset.tab === 'inbox') loadSessions();
    if (item.dataset.tab === 'jobs') loadJobs();
  });
});

// ---------- 职位 Agent ----------
async function loadJobs() {
  const res = await fetch('/api/jobs/');
  const jobs = await res.json();

  filterJob.innerHTML = '<option value="">全部职位</option>' +
    jobs.map(j => `<option value="${j.id}">${escapeHtml(j.title)}</option>`).join('');

  if (!jobs.length) {
    jobsList.innerHTML = '<p class="empty-hint">暂无职位，点击右上角新建</p>';
    return;
  }

  const fullJobs = await Promise.all(
    jobs.map(async j => {
      const r = await fetch(`/api/jobs/${j.id}`);
      return r.json();
    })
  );

  jobsList.innerHTML = fullJobs.map(j => `
    <div class="job-card">
      <h3>${escapeHtml(j.title)} ${j.active ? '' : '<span class="status-tag status-HUMAN_TAKEOVER">已停用</span>'}</h3>
      <div class="meta">
        ID: ${j.id} · 会话: ${jobs.find(x => x.id === j.id)?.session_count || 0}
        ${j.platform_job_id ? ` · 平台ID: ${escapeHtml(j.platform_job_id)}` : ''}
      </div>
      <div class="prompt-preview">${escapeHtml(j.system_prompt)}</div>
      <div class="actions">
        <button class="btn btn-secondary btn-sm" onclick="editJob(${j.id})">编辑 Prompt</button>
      </div>
    </div>
  `).join('');
}

function openJobModal(title, job = null) {
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('editJobId').value = job ? job.id : '';
  document.getElementById('jobTitle').value = job?.title || '';
  document.getElementById('jobPlatformId').value = job?.platform_job_id || '';
  document.getElementById('jobPrompt').value = job?.system_prompt ||
    '你是一位专业的招聘 HR，负责该岗位的候选人沟通。语气友好专业，了解候选人背景后介绍岗位亮点，并引导约面试。';
  document.getElementById('jobActive').checked = job?.active !== false;
  jobModal.classList.remove('hidden');
}

async function editJob(id) {
  const res = await fetch(`/api/jobs/${id}`);
  openJobModal('编辑职位 Agent', await res.json());
}

document.getElementById('btnNewJob').addEventListener('click', () => openJobModal('新建职位 Agent'));
document.getElementById('btnCancelJob').addEventListener('click', () => jobModal.classList.add('hidden'));
document.getElementById('btnSaveJob').addEventListener('click', async () => {
  const id = document.getElementById('editJobId').value;
  const body = {
    title: document.getElementById('jobTitle').value.trim(),
    system_prompt: document.getElementById('jobPrompt').value.trim(),
    active: document.getElementById('jobActive').checked,
    platform_job_id: document.getElementById('jobPlatformId').value.trim() || null,
  };
  if (!body.title || !body.system_prompt) return alert('请填写职位名称和 Prompt');
  const url = id ? `/api/jobs/${id}` : '/api/jobs/';
  await fetch(url, { method: id ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  jobModal.classList.add('hidden');
  loadJobs();
  if (document.getElementById('panel-inbox').classList.contains('active')) loadSessions();
});

// ---------- HR 收件箱 ----------
async function loadSessions() {
  const params = new URLSearchParams();
  if (filterJob.value) params.set('job_id', filterJob.value);
  if (filterStatus.value) params.set('status', filterStatus.value);

  const res = await fetch(`/api/admin/sessions?${params}`);
  sessionsCache = await res.json();
  renderInboxList();

  if (currentSessionId && sessionsCache.some(s => s.id === currentSessionId)) {
    selectSession(currentSessionId, false);
  } else if (sessionsCache.length && !currentSessionId) {
    selectSession(sessionsCache[0].id, false);
  }
}

function renderInboxList() {
  if (!sessionsCache.length) {
    inboxList.innerHTML = '<p class="empty-hint inbox-empty">暂无候选人会话<br><small>可通过 Webhook 或<a href="/chat">消息模拟器</a>产生数据</small></p>';
    return;
  }

  inboxList.innerHTML = sessionsCache.map(s => `
    <div class="inbox-item ${s.id === currentSessionId ? 'active' : ''}" onclick="selectSession(${s.id})">
      <div class="inbox-item-top">
        <strong>${escapeHtml(s.candidate_name || s.platform_uid)}</strong>
        <span class="status-tag status-${s.status}">${STATUS_LABELS[s.status] || s.status}</span>
      </div>
      <div class="inbox-item-job">${escapeHtml(s.job_title)}</div>
      <div class="inbox-item-preview">${escapeHtml(s.last_message_preview || '暂无消息')}</div>
      <div class="inbox-item-meta">
        <span>${s.message_count} 条</span>
        <span>${s.has_resume ? '📄 有简历' : ''}</span>
        <span>${formatTime(s.last_interaction_time)}</span>
      </div>
    </div>
  `).join('');
}

async function selectSession(id, scrollList = true) {
  currentSessionId = id;
  renderInboxList();

  const res = await fetch(`/api/admin/sessions/${id}`);
  if (!res.ok) return;
  const s = await res.json();
  renderSessionDetail(s);
}

function renderSessionDetail(s) {
  const statusLabel = STATUS_LABELS[s.status] || s.status;
  const isHuman = s.status === 'HUMAN_TAKEOVER';

  inboxDetail.innerHTML = `
    <div class="detail-header">
      <div>
        <h2>${escapeHtml(s.candidate_name || '未知候选人')}</h2>
        <p class="detail-sub">
          ${escapeHtml(s.job_title)} · ${escapeHtml(s.platform)} · UID: ${escapeHtml(s.platform_uid)}
        </p>
      </div>
      <div class="detail-actions">
        <span class="status-tag status-${s.status}">${statusLabel}</span>
        ${isHuman
          ? `<button class="btn btn-secondary btn-sm" onclick="releaseToAI(${s.id})">交还 AI</button>`
          : `<button class="btn btn-warning btn-sm" onclick="humanTakeover(${s.id})">人工接管</button>`
        }
      </div>
    </div>

    <div class="detail-resume-panel">
      <h3>📄 候选人简历</h3>
      <div class="resume-upload-row">
        <input type="file" id="detailResumeFile" accept=".pdf,.docx,.txt,.md">
        <button class="btn btn-primary btn-sm" onclick="uploadResumeForSession(${s.id})">上传 / 更新简历</button>
      </div>
      <p id="resumeUploadStatus" class="empty-hint">${s.has_resume ? '已上传简历' : '尚未上传，可从 Boss 直聘导出后在此补充'}</p>
      ${s.resume_summary ? renderResumeSummaryCard(s.resume_summary, escapeHtml) : ''}
      ${s.resume_text && !s.resume_summary
        ? `<div class="resume-summary-box"><strong>简历原文预览</strong><pre>${escapeHtml(s.resume_text.slice(0, 500))}${s.resume_text.length > 500 ? '...' : ''}</pre></div>`
        : ''}
    </div>

    <div class="detail-chat-panel">
      <h3>💬 对话记录 <span class="empty-hint">（左：候选人 · 右：AI Agent 代表 HR 回复）</span></h3>
      <div class="hr-timeline">
        ${s.messages.length
          ? s.messages.map(m => `
            <div class="hr-msg ${m.role === 'user' ? 'hr-msg-candidate' : 'hr-msg-agent'}">
              <div class="hr-msg-label">${m.role === 'user' ? '👤 候选人' : '🤖 AI Agent（我方）'}</div>
              <div class="hr-msg-content">${escapeHtml(m.content)}</div>
              <div class="hr-msg-time">${formatTime(m.created_at)}</div>
            </div>
          `).join('')
          : '<p class="empty-hint">暂无对话，等待候选人通过招聘平台发消息</p>'
        }
      </div>
    </div>
  `;
}

async function uploadResumeForSession(sessionId) {
  const fileInput = document.getElementById('detailResumeFile');
  const statusEl = document.getElementById('resumeUploadStatus');
  const file = fileInput?.files[0];
  if (!file) return alert('请先选择简历文件');

  statusEl.textContent = '上传解析中...';
  const form = new FormData();
  form.append('file', file);
  form.append('auto_parse', 'true');

  try {
    const res = await fetch(`/api/resume/upload/session/${sessionId}`, { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '上传失败');
    statusEl.innerHTML = `✅ 已上传 <strong>${escapeHtml(data.filename)}</strong>（${data.char_count} 字）`;
    selectSession(sessionId);
    loadSessions();
  } catch (err) {
    statusEl.textContent = `❌ ${err.message}`;
  }
}

async function humanTakeover(sessionId) {
  if (!confirm('人工接管后 AI 将不再自动回复，确认？')) return;
  await fetch(`/api/admin/sessions/${sessionId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'HUMAN_TAKEOVER' }),
  });
  selectSession(sessionId);
  loadSessions();
}

async function releaseToAI(sessionId) {
  await fetch(`/api/admin/sessions/${sessionId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'WAITING_CANDIDATE' }),
  });
  selectSession(sessionId);
  loadSessions();
}

document.getElementById('btnRefreshSessions').addEventListener('click', loadSessions);
filterJob.addEventListener('change', () => { currentSessionId = null; loadSessions(); });
filterStatus.addEventListener('change', () => { currentSessionId = null; loadSessions(); });

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text || '';
  return d.innerHTML;
}

function formatTime(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

window.editJob = editJob;
window.selectSession = selectSession;
window.uploadResumeForSession = uploadResumeForSession;
window.humanTakeover = humanTakeover;
window.releaseToAI = releaseToAI;

// 默认打开收件箱
loadJobs();
loadSessions();
