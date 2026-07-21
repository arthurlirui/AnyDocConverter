"""
Tesseract OCR 适配器
"""

from __future__ import annotations

import logging

from PIL import Image

from algo.models.params import OCRParams

logger = logging.getLogger(__name__)


class TesseractOCRAdapter:
    """Tesseract OCR 适配器 — 封装 pytesseract 调用"""

    def __init__(self, params: OCRParams):
        self.params = params
        self._available = None

    def _check_available(self) -> bool:
        """检查 Tesseract 是否可用（结果缓存，避免重复探测）。"""
        if self._available is not None:
            return self._available
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            self._available = True
            logger.info("Tesseract available (lang=%s)", self.params.language)
        except (ImportError, Exception) as e:
            logger.warning("Tesseract not available: %s", e)
            self._available = False
        return self._available

    def recognize(self, image: Image.Image) -> list[dict]:
        """对图片进行文字识别。

        Args:
            image: PIL Image 对象

        Returns:
            list[dict]: [{"text": "...", "confidence": 0.95, "bbox": (x0,y0,x1,y1)}, ...]
        """
        if not self._check_available():
            return []

        try:
            import pytesseract
        except ImportError:
            logger.error("pytesseract not installed")
            return []

        try:
            data = pytesseract.image_to_data(
                image,
                lang=self.params.language,
                output_type=pytesseract.Output.DICT,
            )
        except Exception as e:
            logger.error("Tesseract recognition failed: %s", e)
            return []

        parsed = []
        n = len(data.get("text", []))
        for i in range(n):
            text = data["text"][i].strip()
            if not text:
                continue

            conf_str = data.get("conf", [""])[i]
            try:
                confidence = float(conf_str) / 100.0
            except (ValueError, TypeError):
                confidence = 0.0

            # Tesseract 用 conf=-1 表示“无置信度信息 / 占位项”，
            # 应直接丢弃，而不是当作 0 置信度参与过滤。
            if confidence < 0:
                continue
            if confidence < self.params.min_confidence:
                continue

            x = data.get("left", [0])[i]
            y = data.get("top", [0])[i]
            w = data.get("width", [0])[i]
            h = data.get("height", [0])[i]

            parsed.append({
                "text": text,
                "confidence": confidence,
                "bbox": (x, y, x + w, y + h),
            })

        return parsed
