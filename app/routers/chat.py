"""聊天 Webhook 与 Web 聊天 API"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from openai import APIConnectionError, AuthenticationError, NotFoundError

from app.chat_service import get_all_messages, handle_chat_webhook
from app.database import get_db
from app.schemas import ChatWebhookRequest, ChatWebhookResponse, MessageResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["聊天"])


@router.post("/webhook", response_model=ChatWebhookResponse)
async def chat_webhook(
    payload: ChatWebhookRequest,
    db: AsyncSession = Depends(get_db),
):
    """通用 Webhook：接收招聘平台或 Web 聊天页消息"""
    try:
        session, reply, resume_summary = await handle_chat_webhook(
            db=db,
            platform_uid=payload.platform_uid,
            job_id=payload.job_id,
            message_content=payload.message_content,
            candidate_name=payload.candidate_name,
            platform=payload.platform,
            resume_text=payload.resume_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except APIConnectionError as exc:
        logger.exception("大模型 API 连接失败")
        raise HTTPException(
            status_code=502,
            detail="无法连接百炼大模型，请检查网络；若开了 VPN/代理可尝试关闭，或确认 OPENAI_BASE_URL 正确",
        ) from exc
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail="API Key 无效，请检查 .env 中的 OPENAI_API_KEY") from exc
    except NotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"模型不存在或未开通，请检查 OPENAI_MODEL（当前常见值：qwen-plus / qwen-max）",
        ) from exc
    except Exception as exc:
        logger.exception("Webhook 处理异常")
        err_msg = str(exc)
        if "Connection error" in err_msg or "ConnectError" in err_msg:
            raise HTTPException(
                status_code=502,
                detail="无法连接百炼大模型，请检查网络或代理设置",
            ) from exc
        raise HTTPException(status_code=500, detail="AI 回复生成失败，请稍后重试") from exc

    return ChatWebhookResponse(
        session_id=session.id,
        reply=reply,
        status=session.status,
        resume_summary=resume_summary,
    )


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(session_id: int, db: AsyncSession = Depends(get_db)):
    """获取 Session 完整聊天记录（Web 聊天页刷新记忆用）"""
    messages = await get_all_messages(db, session_id)
    return messages
