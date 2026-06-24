# AI 招聘自动化跟进系统

面向 HR 的 AI Agent 后端：职位独立 Prompt、候选人独立会话记忆、自动回复与定时复聊。

## 功能

- HR 工作台（收件箱、会话详情、简历上传、人工接管）
- 职位 Agent 管理（System Prompt 调教）
- Webhook 对接（通用 / Boss 直聘 / RPA）
- LangChain Agent + 简历解析
- 阿里云百炼（DashScope OpenAI 兼容接口）

## 快速开始

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # 填入百炼 API Key
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- HR 工作台：http://127.0.0.1:8000/admin
- API 文档：http://127.0.0.1:8000/docs
- 消息模拟器（测试）：http://127.0.0.1:8000/chat

## 环境变量

见 [.env.example](.env.example)。**切勿提交 `.env` 文件**（含 API Key）。

## 技术栈

FastAPI · SQLAlchemy 2.0 · SQLite · APScheduler · LangChain · 百炼 qwen
