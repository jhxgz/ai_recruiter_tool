"""简历上传 API（HR 工作台 / 平台对接）"""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.models import ChatSession
from app.resume_service import ALLOWED_EXTENSIONS, process_resume_upload
from app.schemas import ResumeUploadResponse

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/resume", tags=["简历"])


async def _parse_and_save_summary(
    db: AsyncSession,
    resume_text: str,
    candidate,
    auto_parse: bool,
) -> str | None:
    """可选 AI 解析简历并写入候选人记录"""
    resume_summary = candidate.resume_summary
    if auto_parse and settings.agent_mode_enabled:
        from app.agent.tools import parse_resume

        try:
            resume_summary = await parse_resume.ainvoke({"resume_text": resume_text})
            candidate.resume_summary = resume_summary
            await db.flush()
        except Exception:
            logger.exception("简历 AI 解析失败，已保存原文")
    return resume_summary


def _validate_file(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式，请上传: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    return ext


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(..., description="简历文件（PDF / DOCX / TXT）"),
    platform_uid: str = Form(..., description="候选人平台 UID"),
    candidate_name: str = Form(default="", description="候选人姓名"),
    platform: str = Form(default="web", description="来源平台"),
    auto_parse: bool = Form(default=True, description="是否立即 AI 解析简历"),
    db: AsyncSession = Depends(get_db),
):
    """通用简历上传（按 platform_uid 关联候选人）"""
    _validate_file(file)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")

    try:
        resume_text, candidate = await process_resume_upload(
            db=db,
            content=content,
            filename=file.filename,
            platform_uid=platform_uid.strip(),
            candidate_name=candidate_name.strip(),
            platform=platform,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    resume_summary = await _parse_and_save_summary(db, resume_text, candidate, auto_parse)
    preview = resume_text[:300] + ("..." if len(resume_text) > 300 else "")

    return ResumeUploadResponse(
        platform_uid=candidate.platform_uid,
        candidate_id=candidate.id,
        filename=file.filename,
        char_count=len(resume_text),
        text_preview=preview,
        resume_summary=resume_summary,
        message="简历上传成功",
    )


@router.post("/upload/session/{session_id}", response_model=ResumeUploadResponse)
async def upload_resume_for_session(
    session_id: int,
    file: UploadFile = File(..., description="简历文件（PDF / DOCX / TXT）"),
    auto_parse: bool = Form(default=True, description="是否立即 AI 解析简历"),
    db: AsyncSession = Depends(get_db),
):
    """
    HR 工作台：按会话 ID 上传/补充候选人简历

    从会话自动关联候选人，无需手动填写 platform_uid。
    """
    _validate_file(file)

    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.candidate))
        .where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    candidate = session.candidate
    if candidate is None:
        raise HTTPException(status_code=400, detail="会话未关联候选人")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")

    try:
        resume_text, candidate = await process_resume_upload(
            db=db,
            content=content,
            filename=file.filename,
            platform_uid=candidate.platform_uid,
            candidate_name=candidate.name,
            platform=candidate.platform,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    resume_summary = await _parse_and_save_summary(db, resume_text, candidate, auto_parse)
    preview = resume_text[:300] + ("..." if len(resume_text) > 300 else "")

    logger.info("HR 上传简历: session_id=%s candidate=%s", session_id, candidate.platform_uid)

    return ResumeUploadResponse(
        platform_uid=candidate.platform_uid,
        candidate_id=candidate.id,
        session_id=session_id,
        filename=file.filename,
        char_count=len(resume_text),
        text_preview=preview,
        resume_summary=resume_summary,
        message="简历已关联到该候选人",
    )
