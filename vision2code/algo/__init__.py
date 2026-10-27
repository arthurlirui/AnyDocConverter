"""vision2code.algo — 图像/PDF → 可编辑代码转换模块。"""

from .vision_to_code import (
    convert_to_code,
    parse_to_layout,
    generate_code,
    DocumentLayout,
    PageLayout,
    TextElement,
    ImageElement,
)
from .animation import (
    generate_animated_code,
    convert_to_animated_code,
)
from .fidelity import (
    check_fidelity,
    refine_code,
    FidelityReport,
)

__all__ = [
    "convert_to_code",
    "parse_to_layout",
    "generate_code",
    "generate_animated_code",
    "convert_to_animated_code",
    "check_fidelity",
    "refine_code",
    "DocumentLayout",
    "PageLayout",
    "TextElement",
    "ImageElement",
    "FidelityReport",
]
