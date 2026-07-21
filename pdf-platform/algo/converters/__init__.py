"""
格式转换器集合。

每个 ``to_*_converter`` 子模块暴露一个统一签名的模块级函数：

.. code-block:: python

    def convert(file_path: str, params: ConvertParams, output_dir: str) -> str

约定：
- ``file_path``  源 PDF 或图片路径
- ``params``     :class:`~algo.models.params.ConvertParams`，已由 pipeline
                   覆写 ``output_format`` 为当前目标格式
- ``output_dir`` 输出目录（不存在时由实现负责创建）
- 返回值         输出文件路径；多文件输出时返回输出目录路径

新增格式步骤：
    1. 新建 ``to_{format}_converter.py``，实现 ``convert`` 函数；
    2. 在此处导入并加入 ``__all__``；
    3. 在 :mod:`algo.pipeline` 的 ``_FORMAT_MAP`` 注册；
    4. 在 :mod:`algo.utils` 的 ``CONVERTER_FORMATS`` 添加格式标识。
"""

from .to_docx_converter import convert as convert_to_docx
from .to_pptx_converter import convert as convert_to_pptx
from .to_xlsx_converter import convert as convert_to_xlsx
from .to_html_converter import convert as convert_to_html
from .to_jpg_converter import convert as convert_to_jpg
from .to_png_converter import convert as convert_to_png
from .to_markdown_converter import convert as convert_to_markdown
from .to_txt_converter import convert as convert_to_txt

__all__ = [
    "convert_to_docx",
    "convert_to_pptx",
    "convert_to_xlsx",
    "convert_to_html",
    "convert_to_jpg",
    "convert_to_png",
    "convert_to_markdown",
    "convert_to_txt",
]
