"""
API 路由 — 文件上传 + 代码转换。

端点：
- GET  /          → 首页（上传界面）
- POST /api/upload → 上传文件，返回 file_id
- POST /api/convert/{file_id} → 转换文件为可编辑代码
- GET  /api/result/{task_id} → 获取转换结果
- GET  /api/preview/{task_id} → 在浏览器中预览渲染结果
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# ── 模板 ──
templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=templates_dir)

# ── 内存存储（简洁实现，生产环境应用数据库） ──
_uploads: dict[str, dict] = {}  # file_id → {path, filename, size}
_results: dict[str, dict] = {}  # task_id → {code, source_type, page_count, title}

# 支持的文件类型
_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页 — 上传界面。"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "app_name": settings.app_name,
    })


@router.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传 PDF 或图像文件。

    Returns:
        {"file_id": "...", "filename": "...", "size": ...}
    """
    # 验证文件类型
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    # 读取文件
    content = await file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max: {settings.max_upload_size_mb}MB",
        )

    # 保存文件
    file_id = str(uuid.uuid4())
    os.makedirs(settings.upload_dir, exist_ok=True)
    file_path = os.path.join(settings.upload_dir, f"{file_id}{ext}")
    with open(file_path, "wb") as f:
        f.write(content)

    _uploads[file_id] = {
        "path": file_path,
        "filename": file.filename,
        "size": len(content),
    }

    logger.info("File uploaded: %s → %s (%d bytes)", file.filename, file_id, len(content))

    return {"file_id": file_id, "filename": file.filename, "size": len(content)}


@router.post("/api/convert/{file_id}")
async def convert_file_endpoint(file_id: str, animated: bool = False):
    """转换已上传的文件为可编辑代码。

    Query Parameters:
        animated: 是否生成带动画效果的代码（默认 false）

    Returns:
        {"task_id": "...", "status": "completed", "code": "...", ...}
    """
    if file_id not in _uploads:
        raise HTTPException(status_code=404, detail="File not found")

    upload = _uploads[file_id]

    try:
        from app.services.converter import convert_file
        result = convert_file(upload["path"], animated=animated)

        task_id = str(uuid.uuid4())
        _results[task_id] = {
            "code": result.code,
            "source_type": result.source_type,
            "page_count": result.page_count,
            "title": result.title,
            "filename": upload["filename"],
            "animated": animated,
        }

        logger.info("Conversion done: %s → task %s (animated=%s)", file_id, task_id, animated)

        return {
            "task_id": task_id,
            "status": "completed",
            "source_type": result.source_type,
            "page_count": result.page_count,
            "title": result.title,
            "filename": upload["filename"],
            "fidelity_score": round(result.fidelity_score, 3),
            "fidelity_report": result.fidelity_report,
            "animated": animated,
        }

    except Exception as e:
        logger.error("Conversion failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


@router.get("/api/result/{task_id}")
async def get_result(task_id: str):
    """获取转换结果（代码文本）。"""
    if task_id not in _results:
        raise HTTPException(status_code=404, detail="Result not found")

    result = _results[task_id]
    return {
        "task_id": task_id,
        "code": result["code"],
        "source_type": result["source_type"],
        "page_count": result["page_count"],
        "title": result["title"],
        "filename": result["filename"],
    }


@router.get("/api/preview/{task_id}", response_class=HTMLResponse)
async def preview_result(task_id: str):
    """在浏览器中预览渲染结果（直接返回生成的 HTML）。"""
    if task_id not in _results:
        raise HTTPException(status_code=404, detail="Result not found")

    return HTMLResponse(content=_results[task_id]["code"])
