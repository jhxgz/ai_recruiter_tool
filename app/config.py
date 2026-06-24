"""
应用配置模块
通过环境变量或 .env 文件加载配置，支持灵活部署。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置项"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM 配置（OpenAI SDK + 兼容接口，支持阿里云百炼 DashScope）
    # 百炼控制台：https://bailian.console.aliyun.com/ → API-KEY 管理
    openai_api_key: str = ""
    openai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    openai_model: str = "qwen-plus"  # 可选：qwen-turbo / qwen-max / qwen2.5-72b-instruct

    # 数据库
    database_url: str = "sqlite+aiosqlite:///./recruiter.db"

    # 聊天上下文限制（最近 N 条消息）
    chat_history_limit: int = 10

    # 复聊：候选人未回复超过多少小时触发跟进
    follow_up_hours: int = 24

    # 定时任务扫描间隔（分钟）
    scheduler_interval_minutes: int = 10

    # Agent 模式：启用 LangChain 工具调用（简历解析等）
    agent_mode_enabled: bool = True

    # Webhook 鉴权密钥（对接真实平台时校验，留空则不校验）
    webhook_secret: str = ""

    # 简历上传
    resume_upload_dir: str = "./uploads/resumes"
    max_resume_size_mb: int = 10


@lru_cache
def get_settings() -> Settings:
    """获取单例配置对象"""
    return Settings()
