"""管理后台 API：HR 工作台 - 会话收件箱、详情、状态管理"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.chat_service import get_all_messages
from app.database import get_db
from app.models import ChatSession, ChatSessionStatus, Message
from app.schemas import MessageResponse, SessionDetail, SessionListItem, SessionStatusUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["HR 工作台"])

VALID_STATUSES = {s.value for s in ChatSessionStatus}


async def _last_message_preview(db: AsyncSession, session_id: int) -> str | None:
    result = await db.execute(
        select(Message.content)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    content = result.scalar_one_or_none()
    if not content:
        return None
    return content[:80] + ("..." if len(content) > 80 else "")


@router.get("/sessions", response_model=list[SessionListItem])
async def list_sessions(
    job_id: int | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """HR 收件箱：获取候选人会话列表"""
    query = (
        select(ChatSession)
        .options(selectinload(ChatSession.job), selectinload(ChatSession.candidate))
        .order_by(ChatSession.last_interaction_time.desc())
    )
    if job_id:
        query = query.where(ChatSession.job_id == job_id)
    if status:
        query = query.where(ChatSession.status == status)

    result = await db.execute(query)
    sessions = result.scalars().all()

    items: list[SessionListItem] = []
    for s in sessions:
        count_result = await db.execute(
            select(func.count()).select_from(Message).where(Message.session_id == s.id)
        )
        candidate = s.candidate
        job = s.job
        preview = await _last_message_preview(db, s.id)
        items.append(
            SessionListItem(
                id=s.id,
                job_id=s.job_id,
                job_title=job.title if job else "",
                candidate_id=s.candidate_id,
                candidate_name=candidate.name if candidate else "",
                platform_uid=candidate.platform_uid if candidate else "",
                platform=candidate.platform if candidate else "generic",
                status=s.status,
                last_interaction_time=s.last_interaction_time,
                message_count=count_result.scalar() or 0,
                resume_summary=candidate.resume_summary if candidate else None,
                has_resume=bool(candidate and candidate.resume_text),
                last_message_preview=preview,
            )
        )
    return items


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session_detail(session_id: int, db: AsyncSession = Depends(get_db)):
    """HR 视角：会话详情及完整对话记录"""
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.job), selectinload(ChatSession.candidate))
        .where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = await get_all_messages(db, session_id)
    candidate = session.candidate
    job = session.job

    return SessionDetail(
        id=session.id,
        job_id=session.job_id,
        job_title=job.title if job else "",
        candidate_id=session.candidate_id,
        candidate_name=candidate.name if candidate else "",
        platform_uid=candidate.platform_uid if candidate else "",
        platform=candidate.platform if candidate else "generic",
        status=session.status,
        last_interaction_time=session.last_interaction_time,
        resume_text=candidate.resume_text if candidate else None,
        resume_summary=candidate.resume_summary if candidate else None,
        has_resume=bool(candidate and candidate.resume_text),
        messages=[MessageResponse.model_validate(m) for m in messages],
    )


@router.patch("/sessions/{session_id}/status")
async def update_session_status(
    session_id: int,
    payload: SessionStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新会话状态（如人工接管 HUMAN_TAKEOVER）"""
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"无效状态，可选: {VALID_STATUSES}")

    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    session.status = payload.status
    await db.flush()
    logger.info("会话 %s 状态更新为 %s", session_id, payload.status)
    return {"session_id": session_id, "status": session.status}
