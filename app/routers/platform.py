"""
平台 Webhook 路由
统一入口 + Boss 直聘 + RPA 三种对接方式
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat_service import handle_chat_webhook
from app.config import get_settings
from app.database import get_db
from app.models import Job
from app.platforms.boss_zhipin import BossZhipinAdapter
from app.platforms.rpa import RPAAdapter
from app.schemas import BossWebhookPayload, ChatWebhookResponse, RPAWebhookPayload

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/platform", tags=["平台对接"])


async def _resolve_job_by_platform_id(db: AsyncSession, platform_job_id: str) -> int | None:
    """通过 platform_job_id 查找内部 Job.id"""
    result = await db.execute(
        select(Job.id).where(Job.platform_job_id == platform_job_id)
    )
    row = result.scalar_one_or_none()
    return row


def _verify_webhook_secret(x_webhook_secret: str | None) -> None:
    """校验 Webhook 密钥（配置了才启用）"""
    if settings.webhook_secret and x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="Webhook 鉴权失败")


@router.post("/boss/webhook", response_model=ChatWebhookResponse)
async def boss_webhook(
    payload: BossWebhookPayload,
    db: AsyncSession = Depends(get_db),
    x_webhook_secret: str | None = Header(default=None),
):
    """
    Boss 直聘风格 Webhook 入口

    使用前需在管理后台为 Job 设置 platform_job_id 与 Boss 平台职位 ID 对应。
    """
    _verify_webhook_secret(x_webhook_secret)

    adapter = BossZhipinAdapter()

    async def resolver(platform_job_id: str) -> int | None:
        return await _resolve_job_by_platform_id(db, platform_job_id)

    try:
        normalized = await adapter.normalize(payload.model_dump(), resolver)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session, reply, resume_summary = await handle_chat_webhook(
        db=db,
        platform_uid=normalized.platform_uid,
        job_id=normalized.job_id,
        message_content=normalized.message_content,
        candidate_name=normalized.candidate_name,
        platform=normalized.platform,
        resume_text=normalized.resume_text,
    )

    logger.info("[Boss Webhook] uid=%s job=%s", payload.uid, normalized.job_id)
    return ChatWebhookResponse(
        session_id=session.id,
        reply=reply,
        status=session.status,
        resume_summary=resume_summary,
    )


@router.post("/rpa/webhook", response_model=ChatWebhookResponse)
async def rpa_webhook(
    payload: RPAWebhookPayload,
    db: AsyncSession = Depends(get_db),
    x_webhook_secret: str | None = Header(default=None),
):
    """
    RPA 自动化脚本 Webhook 入口

    典型场景：Playwright 监听 Boss 直聘聊天页 DOM 变化，将新消息 POST 到此接口。
    """
    if settings.webhook_secret and payload.rpa_token != settings.webhook_secret:
        _verify_webhook_secret(x_webhook_secret)

    adapter = RPAAdapter()

    async def resolver(platform_job_id: str) -> int | None:
        return await _resolve_job_by_platform_id(db, platform_job_id)

    try:
        normalized = await adapter.normalize(payload.model_dump(), resolver)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session, reply, resume_summary = await handle_chat_webhook(
        db=db,
        platform_uid=normalized.platform_uid,
        job_id=normalized.job_id,
        message_content=normalized.message_content,
        candidate_name=normalized.candidate_name,
        platform=normalized.platform,
        resume_text=normalized.resume_text,
    )

    logger.info("[RPA Webhook] platform=%s uid=%s", payload.platform, normalized.platform_uid)
    return ChatWebhookResponse(
        session_id=session.id,
        reply=reply,
        status=session.status,
        resume_summary=resume_summary,
    )
