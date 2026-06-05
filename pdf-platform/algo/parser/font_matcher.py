"""
字体匹配器 — 将 PDF 中使用的字体匹配到系统可用字体
"""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class FontMatcher:
    """字体匹配器 — 查找系统字体并匹配"""

    def __init__(self):
        self._system_fonts: list[dict] | None = None

    def match(self, font_name: str, fallback: str = "Noto Sans CJK SC") -> str:
        """将 PDF 字体名匹配到系统字体路径。

        Args:
            font_name: PDF 中的字体名称
            fallback: 回退字体名称

        Returns:
            字体文件路径（或空字符串）
        """
        if not font_name:
            return self._find_font_path(fallback)

        system_fonts = self._get_system_fonts()
        matched = []

        for sf in system_fonts:
            if font_name.lower() in sf["name"].lower():
                matched.append(sf)

        if matched:
            # 取最佳匹配（名称最长匹配）
            matched.sort(key=lambda x: len(x["name"]), reverse=True)
            return matched[0]["path"]

        # 尝试回退
        return self._find_font_path(fallback)

    def _get_system_fonts(self) -> list[dict]:
        """获取系统字体列表（带缓存）"""
        if self._system_fonts is not None:
            return self._system_fonts

        fonts = []
        try:
            # 尝试 fc-list (Linux)
            result = subprocess.run(
                ["fc-list", "--format=%{file}\n%{family}\n---\n"],
                capture_output=True, text=True, timeout=10,
            )
            entries = result.stdout.strip().split("---\n")
            for entry in entries:
                lines = entry.strip().split("\n")
                if len(lines) >= 2:
                    path = lines[0].strip()
                    name = lines[1].strip().split(",")[0]  # 取第一个 family
                    fonts.append({"name": name, "path": path})
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.debug("fc-list not available: %s", e)

        self._system_fonts = fonts
        return fonts

    def _find_font_path(self, font_name: str) -> str:
        """按名称查找字体路径"""
        if not font_name:
            return ""
        for sf in self._get_system_fonts():
            if font_name.lower() in sf["name"].lower():
                return sf["path"]
        return ""
