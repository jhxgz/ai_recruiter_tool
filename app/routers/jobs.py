"""职位 Agent 管理 API"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ChatSession, Job
from app.schemas import JobCreate, JobListItem, JobResponse, JobUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["职位 Agent"])


@router.get("/", response_model=list[JobListItem])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    """获取所有职位 Agent 列表"""
    result = await db.execute(select(Job).order_by(Job.id.desc()))
    jobs = result.scalars().all()

    items: list[JobListItem] = []
    for job in jobs:
        count_result = await db.execute(
            select(func.count()).select_from(ChatSession).where(ChatSession.job_id == job.id)
        )
        session_count = count_result.scalar() or 0
        items.append(
            JobListItem(
                id=job.id,
                title=job.title,
                active=job.active,
                platform_job_id=job.platform_job_id,
                session_count=session_count,
            )
        )
    return items


@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(payload: JobCreate, db: AsyncSession = Depends(get_db)):
    """创建新职位及设定 System Prompt"""
    job = Job(
        title=payload.title,
        system_prompt=payload.system_prompt,
        active=payload.active,
        platform_job_id=payload.platform_job_id,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    logger.info("创建职位: id=%s, title=%s", job.id, job.title)
    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """查询单个职位"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail=f"职位不存在: id={job_id}")
    return job


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: int,
    payload: JobUpdate,
    db: AsyncSession = Depends(get_db),
):
    """修改职位 Prompt（支持后期调教）"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail=f"职位不存在: id={job_id}")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, value)

    await db.flush()
    await db.refresh(job)
    logger.info("更新职位: id=%s", job.id)
    return job
