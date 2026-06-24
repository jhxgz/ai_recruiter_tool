"""
Boss 直聘平台 Webhook 适配器
模拟 Boss 直聘推送的消息格式，便于后续对接真实开放平台
"""

from app.platforms.base import NormalizedMessage, PlatformAdapter


class BossZhipinAdapter(PlatformAdapter):
    """
    Boss 直聘消息格式示例：
    {
        "event": "message",
        "uid": "boss_user_123",
        "job_id": "platform_job_456",
        "content": "你好",
        "name": "张三",
        "resume": "5年Python经验..."
    }
    """

    platform_name = "boss"

    async def normalize(self, payload: dict, job_resolver) -> NormalizedMessage:
        platform_job_id = str(payload.get("job_id", ""))
        internal_job_id = await job_resolver(platform_job_id)
        if internal_job_id is None:
            raise ValueError(f"未找到 Boss 平台职位映射: platform_job_id={platform_job_id}")

        return NormalizedMessage(
            platform_uid=f"boss_{payload['uid']}",
            job_id=internal_job_id,
            message_content=payload["content"],
            candidate_name=payload.get("name", ""),
            platform=self.platform_name,
            resume_text=payload.get("resume"),
        )
