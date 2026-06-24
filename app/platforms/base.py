"""
招聘平台消息适配器基类与统一消息模型
将各平台异构 Webhook 载荷转换为系统内部标准格式
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NormalizedMessage:
    """平台无关的标准消息结构"""

    platform_uid: str
    job_id: int
    message_content: str
    candidate_name: str = ""
    platform: str = "generic"
    resume_text: str | None = None


class PlatformAdapter(ABC):
    """平台适配器抽象基类"""

    platform_name: str = "generic"

    @abstractmethod
    async def normalize(self, payload: dict, job_resolver) -> NormalizedMessage:
        """
        将平台原始载荷转为 NormalizedMessage

        Args:
            payload: 原始 JSON 字典
            job_resolver: async callable(platform_job_id) -> internal job_id
        """
