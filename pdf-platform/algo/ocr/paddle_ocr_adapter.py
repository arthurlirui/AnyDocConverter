"""
PaddleOCR 适配器。

面向本地 CPU 部署的 OCR 引擎封装，遵循 PaddleOCR 官方 Python API：

    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang="ch")
    result = ocr.ocr(image_path_or_ndarray, cls=True)

本适配器在官方 API 之上提供以下兼容层：

- **多输入类型**：PIL ``Image`` / numpy ndarray / 文件路径统一处理。
- **预处理**：可选的 EXIF 方向修正、灰度归一化、放大、对比度 / 锐度增强、
  二值化，用于扫描件、截图、收据等困难图像（``enhance_image`` / ``hard``）。
- **结果解析**：兼容 PaddleOCR v2 的嵌套结果格式
  ``[ [ [bbox, (text, score)], ... ] ]`` 与扁平格式。
- **语言别名**：将 Tesseract 风格的语言码（``chi_sim`` / ``eng`` 等）
  映射到 PaddleOCR 的语言标识。
- **临时文件清理**：预处理生成的临时 PNG 在每次 ``recognize`` 后清理，
  避免磁盘泄漏。
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from algo.models.params import OCRParams

logger = logging.getLogger(__name__)


# 前端 / 后端使用的语言别名 → PaddleOCR 语言标识。
# 同时兼容 PaddleOCR 原生码（ch/en/japan/...）与 Tesseract 风格码（chi_sim/eng/...）。
_LANG_MAP = {
    # PaddleOCR common languages
    "ch": "ch",
    "en": "en",
    "japan": "japan",
    "jpn": "japan",
    "korean": "korean",
    "kor": "korean",
    "chinese_cht": "chinese_cht",
    "chi_tra": "chinese_cht",
    # Tesseract-style aliases used by older UI
    "chi_sim": "ch",
    "eng": "en",
}


class PaddleOCRAdapter:
    """PaddleOCR 适配器 — 本地 CPU OCR。

    模型加载采用惰性初始化（:meth:`_lazy_init`），首次 ``recognize`` 才
    真正导入 ``paddleocr`` 并构建 ``PaddleOCR`` 实例，避免无用开销与
    冷启动时对不使用 OCR 的请求造成延迟。
    """

    def __init__(self, params: OCRParams):
        self.params = params
        self._ocr = None
        # 缓存 OCR 预处理生成的临时 PNG 路径，识别后统一清理，
        # 避免每次调用泄漏一份文件到系统 tmp 目录。
        self._tmp_paths: list[str] = []

    def _cleanup_tmp(self) -> None:
        """删除本实例累积的临时预处理 PNG。"""
        for path in self._tmp_paths:
            try:
                from os import remove
                remove(path)
            except OSError:
                # 文件可能已被外部清理，忽略即可
                pass
        self._tmp_paths.clear()

    @property
    def paddle_lang(self) -> str:
        """将 ``params.language`` 映射为 PaddleOCR 语言标识。"""
        return _LANG_MAP.get((self.params.language or "ch").lower(), self.params.language or "ch")

    def _lazy_init(self):
        """惰性初始化 PaddleOCR：导入库并构建实例。

        首次调用时执行，后续直接返回。失败时抛出 :class:`RuntimeError`，
        并在消息中提示常见的 numpy 2.x 不兼容问题。
        """
        if self._ocr is not None:
            return
        try:
            from paddleocr import PaddleOCR

            kwargs = {
                "use_angle_cls": True,
                "lang": self.paddle_lang,
                "show_log": False,
            }
            # CPU is safer for generic server deployment. PaddleOCR v2 accepts use_gpu.
            kwargs["use_gpu"] = False

            self._ocr = PaddleOCR(**kwargs)
            logger.info("PaddleOCR initialized (lang=%s)", self.paddle_lang)
        except Exception as e:
            logger.error("PaddleOCR init failed: %s", e)
            raise RuntimeError(
                "PaddleOCR 初始化失败。请确认已安装 paddlepaddle/paddleocr，"
                "且 numpy 使用 1.x 兼容版本（建议 numpy<2）。原始错误: "
                f"{e}"
            ) from e

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """预处理非标准 / 困难图像。

        PaddleOCR 自身检测能力较强，默认路径保守。当 ``enhance_image`` 或
        ``enhance_mode=hard`` 启用时，对低对比度、微小文字、模糊截图、
        照片、收据、扫描件施加更强的预处理。

        处理顺序：EXIF 方向 → 色彩模式归一化 → 放大 → 对比度 / 锐度 →
        （可选）灰度归一化 + 中值滤波 + 二值化。
        """
        img = ImageOps.exif_transpose(image)
        if img.mode not in ("RGB", "L"):
            bg = Image.new("RGB", img.size, "white")
            if img.mode == "RGBA":
                bg.paste(img, mask=img.getchannel("A"))
                img = bg
            else:
                img = img.convert("RGB")

        enhance = bool(getattr(self.params, "enhance_image", False))
        hard = str(getattr(self.params, "enhance_mode", "standard")).lower() == "hard"

        scale = float(getattr(self.params, "upscale_factor", 1.0) or 1.0)
        if hard and scale < 2.0:
            scale = 2.0
        if scale > 1.0:
            img = img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.Resampling.LANCZOS,
            )

        contrast = float(getattr(self.params, "contrast", 1.15) or 1.15)
        sharpness = float(getattr(self.params, "sharpness", 1.05) or 1.05)
        if hard:
            contrast = max(contrast, 1.6)
            sharpness = max(sharpness, 1.4)

        img = ImageEnhance.Contrast(img).enhance(contrast)
        img = ImageEnhance.Sharpness(img).enhance(sharpness)

        # Hard mode: normalize grayscale and optionally binarize. This helps
        # faint scans and noisy screenshots, but can hurt photos, so it is opt-in.
        if enhance or hard:
            gray = ImageOps.grayscale(img)
            gray = ImageOps.autocontrast(gray)
            gray = gray.filter(ImageFilter.MedianFilter(size=3)) if hard else gray
            if bool(getattr(self.params, "binarize", False)) or hard:
                threshold = 180 if hard else 170
                gray = gray.point(lambda p: 255 if p > threshold else 0)
            img = gray.convert("RGB")

        return img

    def _save_preprocessed_temp(self, image: Image.Image) -> str:
        """预处理图片并落盘为临时 PNG，返回路径（路径会被记录以供清理）。"""
        img = self._preprocess_image(image)
        tmp = tempfile.NamedTemporaryFile(prefix="paddleocr_", suffix=".png", delete=False)
        tmp.close()
        img.save(tmp.name)
        self._tmp_paths.append(tmp.name)
        return tmp.name

    def _to_ocr_input(self, image: Any) -> Any:
        """将文件路径 / PIL 图像转为预处理后的临时 PNG 路径。

        numpy ndarray / cv2 图像直接透传，PaddleOCR 可原生消费。
        """
        if isinstance(image, (str, Path)):
            try:
                return self._save_preprocessed_temp(Image.open(image))
            except Exception:
                # If Pillow cannot open it, pass path through for PaddleOCR.
                return str(image)
        if isinstance(image, Image.Image):
            return self._save_preprocessed_temp(image)
        # numpy array / cv2 image: PaddleOCR can usually consume it directly
        return image

    def _is_ocr_line(self, value: Any) -> bool:
        """判断 value 是否为单条 PaddleOCR 行：``[bbox_points, (text, score)]``。"""
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return False
        bbox, text_info = value
        if not isinstance(bbox, (list, tuple)) or not bbox:
            return False
        if not isinstance(text_info, (list, tuple)) or len(text_info) < 2:
            return False
        return isinstance(text_info[0], str)

    def _iter_lines(self, results: Any):
        """稳健地迭代 PaddleOCR v2 的行条目。

        v2 单图常见输出：``[ [ [bbox, (text, score)], ... ] ]``；
        部分封装可能直接返回 ``[ [bbox, (text, score)], ... ]``。
        本方法兼容两种结构，逐项 yield 合法的行条目。
        """
        if not results:
            return
        if self._is_ocr_line(results):
            yield results
            return
        if isinstance(results, list):
            for item in results:
                if self._is_ocr_line(item):
                    yield item
                elif isinstance(item, list):
                    for line in item:
                        if self._is_ocr_line(line):
                            yield line

    def recognize(self, image: Any) -> list[dict]:
        """识别 PIL 图像 / ndarray / 文件路径中的文字。

        Args:
            image: PIL ``Image``、文件路径或 numpy ndarray。

        Returns:
            识别结果列表，每项形如
            ``{"text": str, "confidence": float, "bbox": (x0, y0, x1, y1)}``，
            bbox 为轴对齐包围盒（左上 / 右下）。识别失败时返回空列表。
        """
        self._lazy_init()
        ocr_input = self._to_ocr_input(image)

        try:
            results = self._ocr.ocr(ocr_input, cls=True)
        except Exception as e:
            logger.error("PaddleOCR recognition failed: %s", e)
            return []
        finally:
            # 无论成功失败都要清理本轮临时文件
            self._cleanup_tmp()

        parsed: list[dict] = []
        for line in self._iter_lines(results):
            try:
                bbox_pts = line[0]
                text_info = line[1]
                text = str(text_info[0]).strip()
                confidence = float(text_info[1])
            except Exception:
                continue
            if not text:
                continue

            # PaddleOCR bbox 为 4 个角点，转为轴对齐包围盒 (x0, y0, x1, y1)
            x0 = min(float(p[0]) for p in bbox_pts)
            y0 = min(float(p[1]) for p in bbox_pts)
            x1 = max(float(p[0]) for p in bbox_pts)
            y1 = max(float(p[1]) for p in bbox_pts)

            parsed.append({
                "text": text,
                "confidence": confidence,
                "bbox": (x0, y0, x1, y1),
            })

        return parsed

