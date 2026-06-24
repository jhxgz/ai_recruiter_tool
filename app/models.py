"""
SQLAlchemy ORM 模型定义
对应 Job / Candidate / ChatSession / Message 四张核心表
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """声明式基类"""


class ChatSessionStatus(str, enum.Enum):
    """会话状态枚举"""

    WAITING_CANDIDATE = "WAITING_CANDIDATE"  # 等待候选人回复
    WAITING_AI = "WAITING_AI"  # 等待 AI 处理（预留）
    FOLLOWED_UP_ONCE = "FOLLOWED_UP_ONCE"  # 已执行一次复聊跟进
    HUMAN_TAKEOVER = "HUMAN_TAKEOVER"  # 人工接管（拼写修正：原需求 TAKOVEOVER）


class MessageRole(str, enum.Enum):
    """消息角色枚举"""

    USER = "user"
    ASSISTANT = "assistant"


class Job(Base):
    """职位 / 智能体表：每个职位拥有独立的 System Prompt"""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="职位名称")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, comment="专属调教提示词")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")
    platform_job_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True, comment="招聘平台侧职位 ID，用于 Webhook 映射"
    )

    # 关联会话
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="job")


class Candidate(Base):
    """候选人表：来自招聘平台的唯一标识"""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform_uid: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True, comment="招聘平台唯一 ID"
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="候选人名称")
    platform: Mapped[str] = mapped_column(
        String(32), default="generic", nullable=False, comment="来源平台: generic/boss/liepin/rpa"
    )
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="原始简历文本")
    resume_summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="AI 解析后的简历摘要")

    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="candidate")


class ChatSession(Base):
    """会话状态表：一个 (职位, 候选人) 对应一个独立记忆 Session"""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=ChatSessionStatus.WAITING_AI.value,
        nullable=False,
        comment="会话状态",
    )
    last_interaction_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="最后交互时间",
    )

    job: Mapped["Job"] = relationship(back_populates="chat_sessions")
    candidate: Mapped["Candidate"] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        order_by="Message.created_at",
    )


class Message(Base):
    """聊天记录表：存储 user / assistant 消息"""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, comment="user 或 assistant")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
