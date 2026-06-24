"""LLM HTTP 客户端工厂（避免系统代理干扰百炼 API 连接）"""

import httpx
from openai import AsyncOpenAI

from app.config import get_settings

settings = get_settings()


def create_openai_async_client() -> AsyncOpenAI:
    """
    创建 OpenAI 兼容异步客户端

    trust_env=False：不读取系统 HTTP_PROXY，避免代理导致 ConnectError
    """
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        http_client=httpx.AsyncClient(trust_env=False, timeout=60.0),
    )


def create_langchain_http_client() -> httpx.AsyncClient:
    """LangChain ChatOpenAI 使用的 httpx 客户端"""
    return httpx.AsyncClient(trust_env=False, timeout=60.0)
