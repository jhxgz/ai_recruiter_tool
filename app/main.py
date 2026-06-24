"""
FastAPI 应用入口
Web 页面 + API 路由 + APScheduler 定时复聊
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.chat_service import run_follow_up_task
from app.config import get_settings
from app.database import init_db
from app.routers import admin, chat, jobs, platform, resume

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()
scheduler = AsyncIOScheduler()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("数据库初始化完成")

    scheduler.add_job(
        run_follow_up_task,
        trigger="interval",
        minutes=settings.scheduler_interval_minutes,
        id="follow_up_scan",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("APScheduler 已启动，复聊扫描间隔=%d 分钟", settings.scheduler_interval_minutes)

    # 启动时打印关键 API，便于确认路由已加载
    api_paths = sorted(p for p in app.openapi()["paths"] if p.startswith("/api/"))
    logger.info("已注册 API 路由 (%d): %s", len(api_paths), ", ".join(api_paths))
    if "/api/resume/upload" not in api_paths:
        logger.warning("简历上传接口未加载，请确认 app/routers/resume.py 存在并重启服务")

    yield

    scheduler.shutdown(wait=False)
    logger.info("APScheduler 已停止")


app = FastAPI(
    title="AI 招聘自动化跟进系统",
    description="Agent 引擎 + Web 聊天 + 管理后台 + 平台对接",
    version="0.2.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(jobs.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(platform.router)
app.include_router(resume.router)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "agent_mode": settings.agent_mode_enabled,
        "model": settings.openai_model,
    }


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """系统首页"""
    return templates.TemplateResponse(request, "index.html")


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """消息模拟器（开发者测试，模拟候选人发消息）"""
    return templates.TemplateResponse(request, "chat.html")


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """HR 工作台"""
    return templates.TemplateResponse(request, "admin.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
