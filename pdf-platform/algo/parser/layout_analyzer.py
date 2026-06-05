"""
版面分析器 — 分析 PDF 页面布局结构（表格检测、栏检测、阅读顺序等）
"""

from __future__ import annotations

import logging
from typing import Optional

from algo.models.params import LayoutParams
from algo.models.pdf_document import Page

logger = logging.getLogger(__name__)


class LayoutAnalyzer:
    """版面分析器"""

    def __init__(self, params: Optional[LayoutParams] = None):
        self.params = params or LayoutParams()

    def analyze(self, page: Page, raw_page=None) -> dict:
        """分析页面布局，返回布局元信息。

        Args:
            page: Page 数据模型
            raw_page: PyMuPDF Page 对象（可选，用于高级分析）

        Returns:
            dict 格式布局信息:
                - columns: 列检测结果
                - tables: 表格区域列表
                - headers_footers: 页眉页脚区域
                - reading_order_hints: 阅读顺序提示
        """
        result = {
            "columns": self._detect_columns(page),
            "tables": [],
            "headers_footers": [],
            "reading_order_hints": [],
        }

        if self.params.detect_tables and raw_page is not None:
            result["tables"] = self._detect_tables(raw_page)

        if self.params.detect_headers_footers:
            result["headers_footers"] = self._detect_headers_footers(page)

        if self.params.reading_order:
            result["reading_order_hints"] = self._get_reading_order(page)

        return result

    def _detect_columns(self, page: Page) -> list[dict]:
        """基于文字块水平位置检测分栏"""
        if not page.text_blocks:
            return []

        # 收集所有文字块的 x 坐标
        x_centers = [
            (tb.bbox[0] + tb.bbox[2]) / 2 for tb in page.text_blocks
        ]

        if not x_centers:
            return []

        mid_x = page.width / 2
        left_blocks = [x for x in x_centers if x < mid_x]
        right_blocks = [x for x in x_centers if x >= mid_x]

        columns = []
        if left_blocks:
            columns.append({"region": "left", "count": len(left_blocks)})
        if right_blocks:
            columns.append({"region": "right", "count": len(right_blocks)})

        return columns

    def _detect_tables(self, raw_page) -> list[dict]:
        """利用 PyMuPDF 的表格检测功能"""
        try:
            tabs = raw_page.find_tables()
            tables = []
            for tab in tabs:
                tables.append({
                    "bbox": tab.bbox,
                    "rows": tab.row_count,
                    "cols": tab.col_count,
                    "header": tab.header is not None,
                })
            return tables
        except Exception as e:
            logger.debug("Table detection failed: %s", e)
            return []

    def _detect_headers_footers(self, page: Page) -> dict:
        """简单检测页眉页脚（靠近页面顶/底部的文字块）"""
        header_blocks = []
        footer_blocks = []

        header_zone = page.height * 0.08  # 顶部 8%
        footer_zone = page.height * 0.92  # 底部 8%

        for tb in page.text_blocks:
            y_center = (tb.bbox[1] + tb.bbox[3]) / 2
            if y_center < header_zone:
                header_blocks.append(tb.text[:50])
            elif y_center > footer_zone:
                footer_blocks.append(tb.text[:50])

        return {
            "headers": header_blocks,
            "footers": footer_blocks,
        }

    def _get_reading_order(self, page: Page) -> list[int]:
        """根据坐标 (y 优先、x 其次) 生成阅读顺序索引"""
        if not page.text_blocks:
            return []

        indexed = list(enumerate(page.text_blocks))
        # 排序: top-to-bottom, then left-to-right
        indexed.sort(key=lambda x: (x[1].bbox[1], x[1].bbox[0]))
        return [idx for idx, _ in indexed]
