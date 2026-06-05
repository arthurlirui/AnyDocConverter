"""
PaddleOCR 适配器
"""

from __future__ import annotations

import logging
from typing import Optional

from algo.models.params import OCRParams

logger = logging.getLogger(__name__)


class PaddleOCRAdapter:
    """PaddleOCR 适配器 — 封装 PaddleOCR 调用"""

    def __init__(self, params: OCRParams):
        self.params = params
        self._ocr = None

    def _lazy_init(self):
        """延迟初始化 PaddleOCR（导入较重）"""
        if self._ocr is not None:
            return
        try:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang=self.params.language,
                show_log=False,
            )
            logger.info("PaddleOCR initialized (lang=%s)", self.params.language)
        except ImportError:
            logger.error(
                "paddleocr not installed. Install with: pip install paddleocr"
            )
            raise
        except Exception as e:
            logger.error("PaddleOCR init failed: %s", e)
            raise

    def recognize(self, image) -> list[dict]:
        """对图片进行文字识别。

        Args:
            image: PIL Image 对象或文件路径

        Returns:
            list[dict]: [{"text": "...", "confidence": 0.95, "bbox": (x0,y0,x1,y1)}, ...]
        """
        self._lazy_init()

        try:
            results = self._ocr.ocr(image, cls=True)
        except Exception as e:
            logger.error("PaddleOCR recognition failed: %s", e)
            return []

        parsed = []
        if results and results[0]:
            for line in results[0]:
                bbox_pts = line[0]  # [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]
                text_info = line[1]
                text = text_info[0]
                confidence = text_info[1]

                x0 = min(p[0] for p in bbox_pts)
                y0 = min(p[1] for p in bbox_pts)
                x1 = max(p[0] for p in bbox_pts)
                y1 = max(p[1] for p in bbox_pts)

                parsed.append({
                    "text": text,
                    "confidence": confidence,
                    "bbox": (x0, y0, x1, y1),
                })

        return parsed
