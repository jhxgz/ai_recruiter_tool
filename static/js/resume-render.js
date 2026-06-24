/**
 * 将 AI 解析的简历 JSON 摘要渲染为 HR 可读卡片
 */

const RESUME_FIELD_LABELS = {
  name: '姓名',
  years_of_experience: '工作年限',
  skills: '技能',
  education: '学历',
  highlights: '亮点',
  job_match_suggestion: '招聘建议',
};

/** 解析 LLM 返回的 JSON 字符串（兼容 markdown 代码块） */
function parseResumeSummaryJson(raw) {
  if (!raw || !String(raw).trim()) return null;

  let text = String(raw).trim();
  const fenced = text.match(/^```(?:json)?\s*([\s\S]*?)```$/i);
  if (fenced) text = fenced[1].trim();

  try {
    return JSON.parse(text);
  } catch {
    const start = text.indexOf('{');
    const end = text.lastIndexOf('}');
    if (start >= 0 && end > start) {
      try {
        return JSON.parse(text.slice(start, end + 1));
      } catch {
        return null;
      }
    }
    return null;
  }
}

/** 渲染为 HTML 卡片（需配合 escapeHtml 使用） */
function renderResumeSummaryCard(raw, escapeHtmlFn) {
  const esc = escapeHtmlFn || ((t) => {
    const d = document.createElement('div');
    d.textContent = t ?? '';
    return d.innerHTML;
  });

  const data = parseResumeSummaryJson(raw);

  if (!data) {
    return `
      <div class="resume-profile-card">
        <div class="resume-profile-title">AI 解析摘要</div>
        <p class="resume-plain-text">${esc(raw)}</p>
      </div>`;
  }

  if (data.error) {
    return `
      <div class="resume-profile-card resume-profile-error">
        <div class="resume-profile-title">AI 解析摘要</div>
        <p>${esc(data.error)}</p>
      </div>`;
  }

  const rows = [];

  if (data.name) {
    rows.push(`
      <div class="resume-field">
        <span class="resume-label">${RESUME_FIELD_LABELS.name}</span>
        <span class="resume-value resume-name">${esc(data.name)}</span>
      </div>`);
  }

  if (data.years_of_experience) {
    rows.push(`
      <div class="resume-field">
        <span class="resume-label">${RESUME_FIELD_LABELS.years_of_experience}</span>
        <span class="resume-value">${esc(String(data.years_of_experience))}</span>
      </div>`);
  }

  if (data.education) {
    rows.push(`
      <div class="resume-field">
        <span class="resume-label">${RESUME_FIELD_LABELS.education}</span>
        <span class="resume-value">${esc(String(data.education))}</span>
      </div>`);
  }

  if (Array.isArray(data.skills) && data.skills.length) {
    rows.push(`
      <div class="resume-field resume-field-block">
        <span class="resume-label">${RESUME_FIELD_LABELS.skills}</span>
        <div class="resume-tags">
          ${data.skills.map(s => `<span class="resume-tag">${esc(String(s))}</span>`).join('')}
        </div>
      </div>`);
  } else if (typeof data.skills === 'string' && data.skills) {
    rows.push(`
      <div class="resume-field resume-field-block">
        <span class="resume-label">${RESUME_FIELD_LABELS.skills}</span>
        <div class="resume-tags">
          ${data.skills.split(/[,，、]/).map(s => s.trim()).filter(Boolean)
            .map(s => `<span class="resume-tag">${esc(s)}</span>`).join('')}
        </div>
      </div>`);
  }

  if (Array.isArray(data.highlights) && data.highlights.length) {
    rows.push(`
      <div class="resume-field resume-field-block">
        <span class="resume-label">${RESUME_FIELD_LABELS.highlights}</span>
        <ul class="resume-highlights">
          ${data.highlights.map(h => `<li>${esc(String(h))}</li>`).join('')}
        </ul>
      </div>`);
  }

  if (data.job_match_suggestion) {
    rows.push(`
      <div class="resume-field resume-suggestion">
        <span class="resume-label">${RESUME_FIELD_LABELS.job_match_suggestion}</span>
        <p class="resume-suggestion-text">${esc(String(data.job_match_suggestion))}</p>
      </div>`);
  }

  if (!rows.length) {
    return `
      <div class="resume-profile-card">
        <div class="resume-profile-title">AI 解析摘要</div>
        <p class="resume-plain-text">${esc(raw)}</p>
      </div>`;
  }

  return `
    <div class="resume-profile-card">
      <div class="resume-profile-title">AI 解析摘要</div>
      <div class="resume-profile-body">${rows.join('')}</div>
    </div>`;
}
