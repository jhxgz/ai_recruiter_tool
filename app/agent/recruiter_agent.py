"""
招聘 Agent 服务
基于 LangChain + OpenAI 兼容接口（支持阿里云百炼）实现工具调用循环
"""

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.agent.tools import RECRUITER_TOOLS, parse_resume
from app.config import get_settings
from app.llm_client import create_langchain_http_client
from app.models import Message

logger = logging.getLogger(__name__)
settings = get_settings()

# 工具名 -> 可调用对象
_TOOL_MAP = {t.name: t for t in RECRUITER_TOOLS}


class RecruiterAgent:
    """带工具调用能力的招聘 Agent"""

    def __init__(self) -> None:
        http_client = create_langchain_http_client()
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.7,
            http_async_client=http_client,
        )
        self.llm_with_tools = self.llm.bind_tools(RECRUITER_TOOLS)
        self.max_tool_rounds = 3

    def _history_to_langchain(
        self,
        system_prompt: str,
        history: list[Message],
        extra_instruction: str | None = None,
        resume_context: str | None = None,
    ) -> list[Any]:
        """将 DB 消息历史转为 LangChain Message 列表"""
        full_system = system_prompt
        if resume_context:
            full_system += f"\n\n【候选人简历摘要】\n{resume_context}"
        if extra_instruction:
            full_system += f"\n\n【附加指令】\n{extra_instruction}"

        messages: list[Any] = [SystemMessage(content=full_system)]
        for msg in history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            else:
                messages.append(AIMessage(content=msg.content))
        return messages

    async def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """执行单个工具调用"""
        tool_fn = _TOOL_MAP.get(tool_name)
        if tool_fn is None:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

        if tool_name == "parse_resume":
            return await parse_resume.ainvoke(tool_args)
        return tool_fn.invoke(tool_args)

    async def generate_reply(
        self,
        system_prompt: str,
        history: list[Message],
        job_title: str = "",
        extra_instruction: str | None = None,
        resume_text: str | None = None,
        resume_summary: str | None = None,
    ) -> tuple[str, str | None]:
        """
        Agent 生成回复，支持多轮工具调用

        Returns:
            (reply_text, new_resume_summary)
        """
        if not settings.openai_api_key:
            raise ValueError("未配置 OPENAI_API_KEY")

        # 若有新简历且尚无摘要，预解析一次
        new_summary = resume_summary
        if resume_text and not resume_summary:
            logger.info("Agent: 检测到新简历，预调用 parse_resume")
            new_summary = await parse_resume.ainvoke({"resume_text": resume_text})

        messages = self._history_to_langchain(
            system_prompt=system_prompt,
            history=history,
            extra_instruction=extra_instruction,
            resume_context=new_summary,
        )

        # 注入职位信息供 get_job_requirements 工具使用
        if job_title:
            messages[0].content += f"\n\n【当前职位】{job_title}"

        logger.info("Agent 开始推理，历史消息数=%d", len(history))

        for round_idx in range(self.max_tool_rounds + 1):
            response = await self.llm_with_tools.ainvoke(messages)
            messages.append(response)

            # 无工具调用则返回最终文本
            if not response.tool_calls:
                reply = (response.content or "").strip()
                return reply, new_summary

            # 执行工具调用
            for tc in response.tool_calls:
                tool_result = await self._execute_tool(tc["name"], tc["args"])
                if tc["name"] == "parse_resume":
                    new_summary = tool_result
                messages.append(
                    ToolMessage(content=tool_result, tool_call_id=tc["id"])
                )
                logger.info("Agent 工具调用: %s (round %d)", tc["name"], round_idx + 1)

        # 超出轮次，取最后一条 AI 消息
        last_ai = next(
            (m for m in reversed(messages) if isinstance(m, AIMessage) and m.content),
            None,
        )
        reply = (last_ai.content if last_ai else "抱歉，我暂时无法回复，请稍后再试。").strip()
        return reply, new_summary


# 全局单例
recruiter_agent = RecruiterAgent()
