"""
Pydantic 请求/响应模型（API 数据校验与序列化）
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------- 职位 Agent ----------


class JobCreate(BaseModel):
    """创建职位请求体"""

    title: str = Field(..., min_length=1, max_length=255, description="职位名称")
    system_prompt: str = Field(..., min_length=1, description="专属 System Prompt")
    active: bool = Field(default=True, description="是否启用")
    platform_job_id: str | None = Field(default=None, description="招聘平台职位 ID")


class JobUpdate(BaseModel):
    """更新职位请求体"""

    title: str | None = Field(default=None, max_length=255)
    system_prompt: str | None = Field(default=None, min_length=1)
    active: bool | None = None
    platform_job_id: str | None = None


class JobResponse(BaseModel):
    """职位响应体"""

    id: int
    title: str
    system_prompt: str
    active: bool
    platform_job_id: str | None = None

    model_config = {"from_attributes": True}


class JobListItem(BaseModel):
    """职位列表项（不含完整 prompt）"""

    id: int
    title: str
    active: bool
    platform_job_id: str | None = None
    session_count: int = 0

    model_config = {"from_attributes": True}


# ---------- 聊天 Webhook ----------


class ChatWebhookRequest(BaseModel):
    """模拟招聘平台消息 Webhook 请求体"""

    platform_uid: str = Field(..., min_length=1, description="招聘平台候选人唯一 ID")
    job_id: int = Field(..., ge=1, description="关联职位 ID")
    message_content: str = Field(..., min_length=1, description="候选人发送的消息内容")
    candidate_name: str = Field(default="", description="候选人名称（首次创建时使用）")
    platform: str = Field(default="generic", description="来源平台标识")
    resume_text: str | None = Field(default=None, description="候选人简历原文（可选）")


class ChatWebhookResponse(BaseModel):
    """Webhook 响应：返回 AI 回复"""

    session_id: int
    reply: str
    status: str
    resume_summary: str | None = None


class MessageResponse(BaseModel):
    """单条消息响应"""

    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- 会话管理 ----------


class SessionListItem(BaseModel):
    """会话列表项"""

    id: int
    job_id: int
    job_title: str
    candidate_id: int
    candidate_name: str
    platform_uid: str
    platform: str
    status: str
    last_interaction_time: datetime
    message_count: int = 0
    resume_summary: str | None = None
    has_resume: bool = False
    last_message_preview: str | None = None


class SessionDetail(BaseModel):
    """会话详情（含完整消息历史）"""

    id: int
    job_id: int
    job_title: str
    candidate_id: int
    candidate_name: str
    platform_uid: str
    platform: str
    status: str
    last_interaction_time: datetime
    resume_text: str | None = None
    resume_summary: str | None = None
    has_resume: bool = False
    messages: list[MessageResponse]


class SessionStatusUpdate(BaseModel):
    """更新会话状态（如人工接管）"""

    status: str = Field(..., description="WAITING_CANDIDATE / HUMAN_TAKEOVER 等")


class ResumeUploadResponse(BaseModel):
    """简历上传响应"""

    platform_uid: str
    candidate_id: int
    session_id: int | None = None
    filename: str
    char_count: int
    text_preview: str
    resume_summary: str | None = None
    message: str


# ---------- 平台 Webhook ----------


class BossWebhookPayload(BaseModel):
    """Boss 直聘风格 Webhook 载荷（模拟真实平台字段）"""

    event: str = Field(default="message", description="事件类型")
    uid: str = Field(..., description="候选人 UID")
    job_id: str = Field(..., description="Boss 平台职位 ID")
    content: str = Field(..., description="消息内容")
    name: str = Field(default="", description="候选人姓名")
    resume: str | None = Field(default=None, description="简历文本")


class RPAWebhookPayload(BaseModel):
    """RPA 浏览器自动化推送载荷"""

    platform: str = Field(default="boss", description="来源平台")
    candidate_id: str = Field(..., description="平台候选人 ID")
    job_id: int | None = Field(default=None, description="系统内部职位 ID")
    platform_job_id: str | None = Field(default=None, description="平台职位 ID")
    message: str = Field(..., description="消息内容")
    candidate_name: str = Field(default="")
    resume_text: str | None = Field(default=None, description="从页面抓取的简历")
    rpa_token: str | None = Field(default=None, description="RPA 鉴权令牌")
