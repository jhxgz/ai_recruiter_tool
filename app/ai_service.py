"""
AI 服务模块
封装 LLM 调用、历史消息拼接与 Prompt 组装逻辑。
通过 OpenAI 兼容 SDK 对接阿里云百炼（DashScope）等 OpenAI 兼容服务。
"""

import logging

from app.config import get_settings
from app.llm_client import create_openai_async_client
from app.models import Message

logger = logging.getLogger(__name__)
settings = get_settings()


class AIService:
    """大模型调用服务"""

    def __init__(self) -> None:
        self.client = create_openai_async_client()
        self.model = settings.openai_model

    def build_messages(
        self,
        system_prompt: str,
        history: list[Message],
        extra_instruction: str | None = None,
    ) -> list[dict[str, str]]:
        """
        组装发送给 LLM 的 messages 列表

        Args:
            system_prompt: 职位专属 System Prompt
            history: 历史消息（已按时间排序，通常为最近 N 条）
            extra_instruction: 附加指令（如复聊场景下的跟进话术要求）
        """
        # 合并系统提示词与附加指令
        full_system = system_prompt
        if extra_instruction:
            full_system = f"{system_prompt}\n\n【附加指令】\n{extra_instruction}"

        messages: list[dict[str, str]] = [{"role": "system", "content": full_system}]

        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        return messages

    async def generate_reply(
        self,
        system_prompt: str,
        history: list[Message],
        extra_instruction: str | None = None,
    ) -> str:
        """
        调用 LLM 生成回复

        Returns:
            AI 生成的文本内容
        """
        if not settings.openai_api_key:
            raise ValueError(
                "未配置 OPENAI_API_KEY（阿里云百炼请在 DashScope 控制台创建 API Key 后填入 .env）"
            )

        messages = self.build_messages(system_prompt, history, extra_instruction)

        logger.info("调用 LLM，模型=%s，历史消息数=%d", self.model, len(history))

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
        )

        reply = response.choices[0].message.content or ""
        return reply.strip()


# 全局单例，供路由与定时任务复用
ai_service = AIService()
