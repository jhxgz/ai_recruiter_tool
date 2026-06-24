"""
简历文件处理服务
支持 PDF / DOCX / TXT 等格式的文本提取与候选人关联
"""

import logging
import re
from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat_service import get_or_create_candidate
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 允许上传的简历格式
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MIME_TO_EXT = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "text/markdown": ".md",
}


def _safe_filename(name: str) -> str:
    """清理文件名，防止路径穿越"""
    base = Path(name).name
    return re.sub(r"[^\w.\-]", "_", base) or "resume"


def extract_text_from_bytes(content: bytes, filename: str) -> str:
    """
    从简历文件二进制内容中提取纯文本

    Raises:
        ValueError: 格式不支持或解析失败
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的文件格式: {ext}，请上传 PDF、DOCX 或 TXT")

    if ext in {".txt", ".md"}:
        for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("无法识别文本文件编码")
        return text.strip()

    if ext == ".pdf":
        try:
            reader = PdfReader(BytesIO(content))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages)
        except Exception as exc:
            raise ValueError(f"PDF 解析失败: {exc}") from exc
        if not text.strip():
            raise ValueError("PDF 中未提取到文本，可能是扫描件，请改用可复制文本的 PDF 或 DOCX")
        return text.strip()

    if ext == ".docx":
        try:
            doc = Document(BytesIO(content))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as exc:
            raise ValueError(f"DOCX 解析失败: {exc}") from exc
        if not text.strip():
            raise ValueError("DOCX 文件内容为空")
        return text.strip()

    raise ValueError(f"不支持的文件格式: {ext}")


def save_resume_file(content: bytes, platform_uid: str, filename: str) -> str:
    """保存原始简历文件到本地，返回相对路径"""
    upload_dir = Path(settings.resume_upload_dir) / _safe_filename(platform_uid)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename)
    file_path = upload_dir / safe_name
    # 同名文件加序号
    if file_path.exists():
        stem, suffix = file_path.stem, file_path.suffix
        for i in range(1, 100):
            candidate = upload_dir / f"{stem}_{i}{suffix}"
            if not candidate.exists():
                file_path = candidate
                break
    file_path.write_bytes(content)
    return str(file_path)


async def process_resume_upload(
    db: AsyncSession,
    content: bytes,
    filename: str,
    platform_uid: str,
    candidate_name: str = "",
    platform: str = "web",
    save_file: bool = True,
) -> tuple[str, object]:
    """
    处理简历上传：提取文本并关联到候选人

    Returns:
        (extracted_text, candidate)
    """
    if len(content) > settings.max_resume_size_mb * 1024 * 1024:
        raise ValueError(f"文件过大，最大允许 {settings.max_resume_size_mb} MB")

    text = extract_text_from_bytes(content, filename)

    if save_file:
        try:
            saved_path = save_resume_file(content, platform_uid, filename)
            logger.info("简历文件已保存: %s", saved_path)
        except Exception:
            logger.exception("简历文件保存失败（文本已提取，继续处理）")

    candidate = await get_or_create_candidate(
        db=db,
        platform_uid=platform_uid,
        name=candidate_name,
        platform=platform,
        resume_text=text,
    )
    return text, candidate
