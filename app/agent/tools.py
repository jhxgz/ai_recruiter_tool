"""
LangChain Agent 工具定义
包含简历解析等招聘场景专用工具
"""

import json
import logging

from langchain_core.tools import tool

from app.config import get_settings
from app.llm_client import create_openai_async_client

logger = logging.getLogger(__name__)
settings = get_settings()


def _clean_json_response(text: str) -> str:
    """去除 LLM 可能包裹的 markdown 代码块，保留纯 JSON"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


async def _llm_extract(prompt: str) -> str:
    """调用 LLM 完成结构化提取（供工具内部使用）"""
    client = create_openai_async_client()
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return (response.choices[0].message.content or "").strip()


@tool
async def parse_resume(resume_text: str) -> str:
    """
    解析候选人简历，提取关键信息（技能、经验年限、教育背景、亮点）。
    当对话中涉及候选人背景、或收到简历内容时调用此工具。
    """
    if not resume_text or not resume_text.strip():
        return json.dumps({"error": "简历内容为空"}, ensure_ascii=False)

    prompt = f"""请从以下简历中提取关键信息，以 JSON 格式返回（不要 markdown 代码块）：
字段：name(姓名), years_of_experience(工作年限), skills(技能数组), education(学历),
highlights(3条亮点), job_match_suggestion(一句招聘建议)

简历内容：
{resume_text[:8000]}
"""
    try:
        result = await _llm_extract(prompt)
        result = _clean_json_response(result)
        logger.info("简历解析完成，长度=%d", len(result))
        return result
    except Exception as exc:
        logger.exception("简历解析失败")
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def get_job_requirements(job_title: str, job_description: str) -> str:
    """
    获取当前职位的核心要求摘要，用于回答候选人关于岗位的提问。
    job_title: 职位名称
    job_description: 职位描述或 Agent 策略中的关键要求
    """
    return json.dumps(
        {
            "title": job_title,
            "requirements_summary": job_description[:2000],
            "tip": "请结合以上要求，专业且友好地回答候选人问题",
        },
        ensure_ascii=False,
    )


# 导出所有工具列表
RECRUITER_TOOLS = [parse_resume, get_job_requirements]
