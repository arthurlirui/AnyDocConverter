"""
转换服务 — 调用 vision2code.algo 模块完成图像/PDF → 代码转换。

作为 API 层与算法层之间的桥梁，负责：
- 文件路径管理
- 临时文件清理
- 错误处理与日志
- 保真度检查与迭代优化
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """转换结果。"""
    code: str  # 生成的 HTML/CSS 代码
    source_type: str  # "pdf" or "image"
    page_count: int
    title: str
    fidelity_score: float = 0.0  # 保真度分数 0-1
    fidelity_report: dict | None = None  # 详细保真度报告


def convert_file(file_path: str, animated: bool = False) -> ConversionResult:
    """转换 PDF/图像文件为可编辑代码。

    流程：
    1. 解析文件 → DocumentLayout
    2. 生成 HTML/CSS 代码（静态或带动画效果）
    3. 保真度检查 + 迭代优化
    4. 返回优化后的代码和保真度报告

    Args:
        file_path: 源文件绝对路径
        animated: 是否生成带动画效果的代码（入场动画 + 播放控制）

    Returns:
        ConversionResult 包含生成的代码和保真度信息

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 不支持的文件类型
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Source file not found: {file_path}")

    # 将 algo 模块加入 path
    import sys
    algo_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "algo")
    algo_abs = os.path.abspath(algo_path)
    if algo_abs not in sys.path:
        sys.path.insert(0, algo_abs)

    from vision_to_code import parse_to_layout, generate_code
    from animation import generate_animated_code
    from fidelity import refine_code, check_fidelity

    # 阶段 1: 解析布局
    layout = parse_to_layout(file_path)

    # 阶段 2: 生成代码（静态或动画）
    if animated:
        initial_code = generate_animated_code(layout)
    else:
        initial_code = generate_code(layout)

    # 阶段 3: 保真度检查 + 迭代优化
    refined_code, report = refine_code(file_path, initial_code, layout, max_iterations=2)

    logger.info(
        "Conversion complete: %s → %d chars of HTML, %d pages, fidelity=%.2f, animated=%s",
        os.path.basename(file_path),
        len(refined_code),
        len(layout.pages),
        report.overall_score,
        animated,
    )

    # 构建保真度报告摘要
    fidelity_report = {
        "overall_score": round(report.overall_score, 3),
        "total_elements": report.total_elements,
        "matched_elements": report.matched_elements,
        "text_coverage": round(report.text_coverage, 3),
        "image_coverage": round(report.image_coverage, 3),
        "position_accuracy": round(report.position_accuracy, 3),
        "issues_count": len(report.issues),
        "issues": report.issues[:10],
    }

    return ConversionResult(
        code=refined_code,
        source_type=layout.source_type,
        page_count=len(layout.pages),
        title=layout.title,
        fidelity_score=report.overall_score,
        fidelity_report=fidelity_report,
    )
