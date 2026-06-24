"""
聊天业务逻辑
包含 Webhook 消息处理与定时复聊核心流程
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai_service import ai_service
from app.config import get_settings
from app.models import (
    Candidate,
    ChatSession,
    ChatSessionStatus,
    Job,
    Message,
    MessageRole,
)

logger = logging.getLogger(__name__)
settings = get_settings()

FOLLOW_UP_EXTRA_INSTRUCTION = (
    "候选人已经24小时未回复，请结合上下文生成一句简短热情的跟进话术，吸引回复。"
    "不要重复之前说过的话，语气自然友好，控制在 80 字以内。"
)


async def _generate_ai_reply(
    job: Job,
    history: list[Message],
    extra_instruction: str | None = None,
    resume_text: str | None = None,
    resume_summary: str | None = None,
) -> tuple[str, str | None]:
    """
    根据配置选择 Agent 模式或基础 LLM 模式生成回复

    Returns:
        (reply_text, updated_resume_summary)
    """
    if settings.agent_mode_enabled:
        from app.agent.recruiter_agent import recruiter_agent

        return await recruiter_agent.generate_reply(
            system_prompt=job.system_prompt,
            history=history,
            job_title=job.title,
            extra_instruction=extra_instruction,
            resume_text=resume_text,
            resume_summary=resume_summary,
        )

    reply = await ai_service.generate_reply(
        system_prompt=job.system_prompt,
        history=history,
        extra_instruction=extra_instruction,
    )
    return reply, resume_summary


async def get_or_create_candidate(
    db: AsyncSession,
    platform_uid: str,
    name: str = "",
    platform: str = "generic",
    resume_text: str | None = None,
) -> Candidate:
    """根据 platform_uid 查找或创建候选人"""
    result = await db.execute(
        select(Candidate).where(Candidate.platform_uid == platform_uid)
    )
    candidate = result.scalar_one_or_none()

    if candidate is None:
        candidate = Candidate(
            platform_uid=platform_uid,
            name=name or platform_uid,
            platform=platform,
            resume_text=resume_text,
        )
        db.add(candidate)
        await db.flush()
        logger.info("创建新候选人: platform_uid=%s platform=%s", platform_uid, platform)
    else:
        if name and candidate.name != name:
            candidate.name = name
        if platform and candidate.platform != platform:
            candidate.platform = platform
        if resume_text:
            candidate.resume_text = resume_text

    return candidate


async def get_or_create_session(
    db: AsyncSession,
    job_id: int,
    candidate_id: int,
) -> ChatSession:
    """根据 (job_id, candidate_id) 查找或创建聊天 Session"""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.job_id == job_id,
            ChatSession.candidate_id == candidate_id,
        )
    )
    session = result.scalar_one_or_none()

    if session is None:
        session = ChatSession(
            job_id=job_id,
            candidate_id=candidate_id,
            status=ChatSessionStatus.WAITING_AI.value,
        )
        db.add(session)
        await db.flush()
        logger.info("创建新会话: job_id=%s, candidate_id=%s", job_id, candidate_id)

    return session


async def get_recent_messages(
    db: AsyncSession,
    session_id: int,
    limit: int | None = None,
) -> list[Message]:
    """获取 Session 最近 N 条历史消息（按时间升序）"""
    limit = limit or settings.chat_history_limit

    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(result.scalars().all())
    messages.reverse()
    return messages


async def get_all_messages(db: AsyncSession, session_id: int) -> list[Message]:
    """获取 Session 全部聊天记录（Web 页展示记忆用）"""
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
    )
    return list(result.scalars().all())


async def handle_chat_webhook(
    db: AsyncSession,
    platform_uid: str,
    job_id: int,
    message_content: str,
    candidate_name: str = "",
    platform: str = "generic",
    resume_text: str | None = None,
) -> tuple[ChatSession, str, str | None]:
    """
    处理招聘平台 Webhook 消息，返回 (session, ai_reply, resume_summary)
    """
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise ValueError(f"职位不存在: job_id={job_id}")
    if not job.active:
        raise ValueError(f"职位已停用: job_id={job_id}")

    # 人工接管状态下不自动回复
    candidate = await get_or_create_candidate(
        db, platform_uid, candidate_name, platform, resume_text
    )
    session = await get_or_create_session(db, job_id, candidate.id)

    if session.status == ChatSessionStatus.HUMAN_TAKEOVER.value:
        user_message = Message(
            session_id=session.id,
            role=MessageRole.USER.value,
            content=message_content,
        )
        db.add(user_message)
        session.last_interaction_time = datetime.now(timezone.utc)
        await db.flush()
        return session, "[人工接管中，AI 暂不自动回复]", candidate.resume_summary

    user_message = Message(
        session_id=session.id,
        role=MessageRole.USER.value,
        content=message_content,
    )
    db.add(user_message)
    await db.flush()

    history = await get_recent_messages(db, session.id)
    ai_reply, new_summary = await _generate_ai_reply(
        job=job,
        history=history,
        resume_text=resume_text or candidate.resume_text,
        resume_summary=candidate.resume_summary,
    )

    if new_summary and new_summary != candidate.resume_summary:
        candidate.resume_summary = new_summary

    assistant_message = Message(
        session_id=session.id,
        role=MessageRole.ASSISTANT.value,
        content=ai_reply,
    )
    db.add(assistant_message)

    session.status = ChatSessionStatus.WAITING_CANDIDATE.value
    session.last_interaction_time = datetime.now(timezone.utc)

    await db.flush()
    logger.info("Webhook 处理完成: session_id=%s agent=%s", session.id, settings.agent_mode_enabled)

    return session, ai_reply, candidate.resume_summary


async def run_follow_up_task() -> None:
    """定时复聊任务（由 APScheduler 调用）"""
    from app.database import AsyncSessionLocal

    now = datetime.now(timezone.utc)
    threshold = now - timedelta(hours=settings.follow_up_hours)

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(ChatSession)
                .options(selectinload(ChatSession.job), selectinload(ChatSession.candidate))
                .where(
                    ChatSession.status == ChatSessionStatus.WAITING_CANDIDATE.value,
                    ChatSession.last_interaction_time <= threshold,
                )
            )
            sessions = result.scalars().all()

            if not sessions:
                logger.debug("复聊扫描：暂无需要跟进的会话")
                return

            logger.info("复聊扫描：发现 %d 个待跟进会话", len(sessions))

            for session in sessions:
                job = session.job
                candidate = session.candidate
                if job is None or not job.active:
                    continue

                history = await get_recent_messages(db, session.id)
                follow_up_text, _ = await _generate_ai_reply(
                    job=job,
                    history=history,
                    extra_instruction=FOLLOW_UP_EXTRA_INSTRUCTION,
                    resume_summary=candidate.resume_summary if candidate else None,
                )

                follow_up_message = Message(
                    session_id=session.id,
                    role=MessageRole.ASSISTANT.value,
                    content=follow_up_text,
                )
                db.add(follow_up_message)

                session.status = ChatSessionStatus.FOLLOWED_UP_ONCE.value
                session.last_interaction_time = now

                candidate_name = candidate.name if candidate else "未知"
                logger.info(
                    "[模拟发送复聊] session_id=%s, candidate=%s, job=%s, content=%s",
                    session.id,
                    candidate_name,
                    job.title,
                    follow_up_text,
                )

            await db.commit()
            logger.info("复聊任务完成，共处理 %d 个会话", len(sessions))

        except Exception:
            await db.rollback()
            logger.exception("复聊任务执行失败")
            raise
