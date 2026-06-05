"""
布局渲染器 — 重建时处理页面布局
"""

from __future__ import annotations

import logging
from typing import Optional

from algo.models.params import ConvertParams
from algo.models.pdf_document import Page

logger = logging.getLogger(__name__)


class LayoutRenderer:
    """布局渲染 — 页面背景、边距、页眉页脚等"""

    def __init__(self, params: ConvertParams):
        self.params = params

    def post_process(self, raw_page, page: Page):
        """对 PyMuPDF Page 进行布局后处理"""
        _ = page  # 预留
        # 未来可在此添加：页眉页脚同步、页面边距调整等
        pass
