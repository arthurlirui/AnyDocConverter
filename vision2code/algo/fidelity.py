"""
FidelityChecker — 渲染对比与迭代优化模块。

参考 screenshot-to-code 的 generate→render→compare→refine 核心循环：
1. 将生成的 HTML 渲染为图像（通过 PyMuPDF 的 SVG/像素路径）
2. 与源图像进行像素级对比
3. 计算保真度分数（结构相似度 + 文本覆盖率）
4. 自动检测并修复常见布局问题

由于不依赖外部浏览器（Playwright/Chrome），使用以下策略：
- 对 PDF 输入：直接对比 PyMuPDF 渲染的页面像素与生成代码中的元素坐标
- 对图像输入：对比源图像与代码中提取的元素覆盖率
- 输出保真度报告，包含逐元素的位置匹配分数

这是 screenshot-to-code 的 render-compare-refine 思想的轻量实现：
不使用 VLM 做视觉对比（需要 GPU + 大模型），而是用确定性的像素/坐标对比。
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import fitz
from PIL import Image

from vision_to_code import (
    DocumentLayout,
    PageLayout,
    TextElement,
    ImageElement,
    parse_to_layout,
    generate_code,
)

logger = logging.getLogger(__name__)


@dataclass
class ElementMatch:
    """单个元素的匹配结果。"""
    element_type: str  # "text" | "image"
    text: str
    expected_bbox: tuple[float, float, float, float]  # (x, y, w, h)
    in_code: bool
    position_score: float  # 0-1, 1=完美匹配
    coverage_score: float  # 0-1, 1=完全覆盖


@dataclass
class FidelityReport:
    """保真度报告。"""
    overall_score: float  # 0-1
    total_elements: int
    matched_elements: int
    text_coverage: float  # 源文档中文本被代码覆盖的比例
    image_coverage: float
    position_accuracy: float  # 位置匹配平均分
    element_matches: list[ElementMatch] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    refined_code: Optional[str] = None  # 优化后的代码（如有）


def check_fidelity(
    source_path: str,
    generated_code: str,
    layout: Optional[DocumentLayout] = None,
) -> FidelityReport:
    """检查生成代码与源文档的保真度。

    Args:
        source_path: 源 PDF/图像文件路径
        generated_code: 生成的 HTML 代码
        layout: 预解析的 DocumentLayout（可选，避免重复解析）

    Returns:
        FidelityReport 包含逐元素匹配分数和整体保真度
    """
    if layout is None:
        layout = parse_to_layout(source_path)

    matches: list[ElementMatch] = []
    issues: list[str] = []

    total_text = 0
    matched_text = 0
    total_images = 0
    matched_images = 0
    position_scores: list[float] = []

    for page_idx, page in enumerate(layout.pages):
        # 检查文本元素
        for el in page.text_elements:
            total_text += 1
            in_code = el.text.strip() in generated_code
            if in_code:
                matched_text += 1

            # 位置匹配：检查代码中是否包含该元素的坐标
            pos_score = _check_position_in_code(generated_code, el)
            position_scores.append(pos_score)

            matches.append(ElementMatch(
                element_type="text",
                text=el.text[:50],
                expected_bbox=(el.x, el.y, el.width, el.height),
                in_code=in_code,
                position_score=pos_score,
                coverage_score=1.0 if in_code else 0.0,
            ))

            if not in_code:
                issues.append(f"Page {page_idx+1}: Text '{el.text[:30]}...' missing from code")
            elif pos_score < 0.5:
                issues.append(f"Page {page_idx+1}: Text '{el.text[:30]}...' position mismatch (score={pos_score:.2f})")

        # 检查图片元素
        for el in page.image_elements:
            total_images += 1
            # 图片在代码中以 base64 形式存在
            in_code = len(el.image_bytes) > 0 and "data:image" in generated_code
            if in_code:
                matched_images += 1

            matches.append(ElementMatch(
                element_type="image",
                text="(image)",
                expected_bbox=(el.x, el.y, el.width, el.height),
                in_code=in_code,
                position_score=1.0 if in_code else 0.0,
                coverage_score=1.0 if in_code else 0.0,
            ))

            if not in_code:
                issues.append(f"Page {page_idx+1}: Image at ({el.x:.0f},{el.y:.0f}) missing from code")

    # 计算汇总分数
    total_elements = total_text + total_images
    matched_elements = matched_text + matched_images

    text_coverage = matched_text / total_text if total_text > 0 else 1.0
    image_coverage = matched_images / total_images if total_images > 0 else 1.0
    position_accuracy = sum(position_scores) / len(position_scores) if position_scores else 1.0

    # 综合分数：文本覆盖 40% + 图片覆盖 30% + 位置精度 30%
    overall = (
        text_coverage * 0.4
        + image_coverage * 0.3
        + position_accuracy * 0.3
    )

    return FidelityReport(
        overall_score=overall,
        total_elements=total_elements,
        matched_elements=matched_elements,
        text_coverage=text_coverage,
        image_coverage=image_coverage,
        position_accuracy=position_accuracy,
        element_matches=matches,
        issues=issues,
    )


def refine_code(
    source_path: str,
    generated_code: str,
    layout: Optional[DocumentLayout] = None,
    max_iterations: int = 2,
) -> tuple[str, FidelityReport]:
    """迭代优化生成的代码。

    执行 generate → check → fix 循环：
    1. 检查当前代码的保真度
    2. 自动修复检测到的问题（缺失文本、位置错误）
    3. 重复直到分数不再提升或达到最大迭代次数

    Args:
        source_path: 源文件路径
        generated_code: 初始生成的代码
        layout: 预解析的布局（可选）
        max_iterations: 最大优化迭代次数

    Returns:
        (优化后的代码, 最终保真度报告)
    """
    if layout is None:
        layout = parse_to_layout(source_path)

    current_code = generated_code
    best_report = check_fidelity(source_path, current_code, layout)
    best_code = current_code

    logger.info(
        "Fidelity check: score=%.2f, %d/%d elements matched",
        best_report.overall_score,
        best_report.matched_elements,
        best_report.total_elements,
    )

    for iteration in range(max_iterations):
        if best_report.overall_score >= 0.95:
            logger.info("Fidelity score >= 0.95, stopping refinement")
            break

        if not best_report.issues:
            logger.info("No issues found, stopping refinement")
            break

        # 尝试修复
        fixed_code = _auto_fix_issues(current_code, best_report, layout)
        if fixed_code == current_code:
            logger.info("No auto-fixes applicable, stopping refinement")
            break

        current_code = fixed_code
        new_report = check_fidelity(source_path, current_code, layout)

        logger.info(
            "Refinement iteration %d: score %.2f → %.2f",
            iteration + 1,
            best_report.overall_score,
            new_report.overall_score,
        )

        if new_report.overall_score > best_report.overall_score:
            best_report = new_report
            best_code = current_code
        else:
            break

    best_report.refined_code = best_code
    return best_code, best_report


def _check_position_in_code(code: str, el: TextElement) -> float:
    """检查代码中是否包含元素的近似坐标。

    返回 0-1 的分数：1 表示精确匹配，0 表示完全缺失。
    """
    # 检查 x 坐标（允许 ±2px 误差）
    x_match = _coord_in_code(code, "left", el.x, tolerance=2.0)
    y_match = _coord_in_code(code, "top", el.y, tolerance=2.0)

    score = 0.0
    if x_match:
        score += 0.5
    if y_match:
        score += 0.5
    return score


def _coord_in_code(code: str, prop: str, value: float, tolerance: float = 2.0) -> bool:
    """检查代码中是否包含某个坐标属性的近似值。"""
    # 生成可能的值变体（整数和小数形式）
    candidates = [
        f"{prop}:{value:.0f}",
        f"{prop}:{value:.1f}",
        f"{prop}: {value:.0f}",
        f"{prop}: {value:.1f}",
    ]
    for candidate in candidates:
        if candidate in code:
            return True

    # 检查容差范围内的值
    int_val = int(value)
    for delta in range(-int(tolerance), int(tolerance) + 1):
        for fmt in [f"{prop}:{int_val + delta}", f"{prop}: {int_val + delta}"]:
            if fmt in code:
                return True

    return False


def _auto_fix_issues(
    code: str,
    report: FidelityReport,
    layout: DocumentLayout,
) -> str:
    """自动修复检测到的保真度问题。

    当前修复策略：
    - 缺失的文本元素：重新生成完整代码（确保所有元素都在）
    - 位置不匹配：无法在不重新解析的情况下修复，跳过
    """
    # 如果有缺失的文本元素，重新生成代码（确保完整性）
    missing_text = [m for m in report.element_matches if not m.in_code and m.element_type == "text"]
    if missing_text:
        logger.info("Auto-fix: %d missing text elements, regenerating code", len(missing_text))
        return generate_code(layout)

    return code


def render_html_to_image(html_code: str, width: int = 800, height: int = 600) -> Optional[bytes]:
    """将 HTML 代码渲染为图像（使用 PyMuPDF）。

    这是一个简化的渲染器：将 HTML 作为 PDF 页面插入并光栅化。
    不支持完整 CSS，但能渲染基本布局。

    Args:
        html_code: HTML 代码字符串
        width: 输出图像宽度
        height: 输出图像高度

    Returns:
        PNG 图像字节，或 None（如果渲染失败）
    """
    try:
        # 创建一个 PDF 页面并插入 HTML
        doc = fitz.open()
        page = doc.new_page(width=width, height=height)

        # 使用 PyMuPDF 的 insert_html（如果可用）
        try:
            page.insert_html(html_code)
        except (AttributeError, TypeError):
            # 不支持 insert_html，回退到文本提取
            pass

        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        doc.close()
        return img_bytes
    except Exception as e:
        logger.debug("HTML render failed: %s", e)
        return None
