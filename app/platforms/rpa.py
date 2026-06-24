"""
RPA 浏览器自动化适配器
接收 Playwright / Selenium 等 RPA 脚本从招聘页面抓取的消息
"""

from app.platforms.base import NormalizedMessage, PlatformAdapter


class RPAAdapter(PlatformAdapter):
    """
    RPA 推送格式：
    {
        "platform": "boss",
        "candidate_id": "12345",
        "job_id": 1,                    // 系统内部 ID（优先）
        "platform_job_id": "ext_456",   // 或使用平台 ID 映射
        "message": "候选人消息",
        "candidate_name": "李四",
        "resume_text": "从页面 DOM 提取的简历",
        "rpa_token": "optional_secret"
    }
    """

    platform_name = "rpa"

    async def normalize(self, payload: dict, job_resolver) -> NormalizedMessage:
        platform = payload.get("platform", "boss")
        candidate_id = payload["candidate_id"]

        # 优先使用内部 job_id，否则通过 platform_job_id 映射
        job_id = payload.get("job_id")
        if not job_id:
            platform_job_id = payload.get("platform_job_id")
            if not platform_job_id:
                raise ValueError("RPA 载荷缺少 job_id 或 platform_job_id")
            job_id = await job_resolver(str(platform_job_id))
            if job_id is None:
                raise ValueError(f"未找到职位映射: {platform_job_id}")

        return NormalizedMessage(
            platform_uid=f"{platform}_{candidate_id}",
            job_id=int(job_id),
            message_content=payload["message"],
            candidate_name=payload.get("candidate_name", ""),
            platform=f"rpa_{platform}",
            resume_text=payload.get("resume_text"),
        )
