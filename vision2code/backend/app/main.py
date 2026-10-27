"""
Vision2Code — FastAPI 主应用入口。

启动：
    cd vision2code/backend
    python -m app.main

或使用 uvicorn：
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import sys

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 确保 algo 模块在 path 中
_algo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "algo"))
if _algo_path not in sys.path:
    sys.path.insert(0, _algo_path)

app = FastAPI(
    title=settings.app_name,
    description="将 PDF 或图像转换为可编辑的 HTML/CSS 代码",
    version="1.0.0",
)

# 静态文件
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# 路由
app.include_router(router)


@app.get("/api/health")
async def health():
    """健康检查端点。"""
    return {"status": "ok", "app": settings.app_name}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
