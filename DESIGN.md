# 端到端文档重建流水线 — 设计文档

## 概述

本文档描述 AnyDocConverter 中新增的**结构化文档重建流水线**的设计与实现。
该流水线将 PDF 或图片（照片、截图、海报）精确转换为可编辑的 Word (.docx) 和
PowerPoint (.pptx) 文档，保留文本、表格、图片、阅读顺序和字体格式。

核心改进：将原有的"直接转换"架构升级为**三阶段解耦架构**：

```
Parse → DocumentModel (IR) → Generate
```

## 研究背景

在设计本方案前，调研了当前主流开源基于大模型/深度学习的文档转换工具：

| 工具 | 架构 | Stars | 关键技术 |
|------|------|-------|---------|
| **MinerU** | 多模块 + VLM 分层 | 82k | LayoutLMv3 版面检测 + UniMERNet 公式 + TableMaster 表格 + PaddleOCR |
| **Docling** | 模块化 + GraniteDocling VLM | 69k | RT-DETR 版面 + TableFormer 表格 + 统一 DoclingDocument IR |
| **Marker** | 混合 (pdftext + Surya VLM) | 41k | Surya VLM 650M + 选择性 VLM 调用 + CPU 表格启发式 |
| **Nougat** | 端到端单模型 | 10k | Swin Transformer + mBART 直接生成 markup |
| **PaddleOCR PP-StructureV3** | 多组件管线 | 92k | 版面分析 + 表格结构 + OCR + 已支持 DOCX 导出 |
| **Surya** | 单 VLM 集成 | 22k | 650M VLM 同时做 OCR + 版面 + 阅读顺序 + 表格 |

### 从调研中提取的关键设计决策

1. **统一中间表示 (IR)**：MinerU、Docling、SmolDocling 都使用统一的文档模型
   （DoclingDocument / DocTags / Content List）作为解析与生成之间的桥梁。
   → 我们采用 `DocumentModel` (Pydantic) 作为 IR。

2. **分层解析策略**：MinerU 的 Flash/Basic/Standard/Advanced 四级解析、Marker 的
   fast/balanced 模式都表明：有文本层的 PDF 用快速路径（直接提取），无文本层的
   用 OCR 路径。
   → 我们自动检测文本层，数字 PDF 走 PyMuPDF，扫描件/图片走 PaddleOCR。

3. **阅读顺序在解析阶段确定**：Surya 的 VLM 直接输出 0-indexed 阅读顺序，
   LayoutReader 用 seq2seq 重排。我们把阅读顺序作为 IR 的一等公民
   (`reading_order` 字段)，在解析阶段计算。

4. **DOCX = 语义重排流，PPTX = 绝对定位画布**：DOCX 本质是 reflowable 格式，
   python-docx 不支持浮动定位；PPTX 本质是 fixed-layout，python-pptx 天然支持
   绝对坐标。因此两种输出用不同策略：
   - DOCX：语义结构化（标题→Heading，文本→Paragraph，表格→Table，多列→Section Columns）
   - PPTX：坐标定位（文本框/图片/表格按归一化 bbox 放置）

5. **字体元数据保留**：pdf2docx 的做法是提取 PyMuPDF 的字体信息（字体名、字号、
   粗体、颜色）并透传到 docx runs。VLM 方案（Surya、GOT-OCR）通常丢失字体信息。
   → 我们在数字 PDF 路径完整保留 run 级字体元数据。

6. **优雅降级**：Marker 的 fast 模式、Docling 的标准管线都设计了回退机制。
   → 结构化流水线失败时自动回退到原有 converter。

## 架构

```
                    ┌──────────────────────────────┐
                    │       pipeline.convert()      │
                    └──────────┬───────────────────┘
                               │
                    ┌──────────▼───────────────────┐
                    │  target_format ∈ {docx,pptx}? │
                    └──────┬──────────────┬────────┘
                          Yes             No
                           │               │
               ┌───────────▼───────┐   ┌──▼──────────────────┐
               │ Structure Pipeline│   │ Legacy Converter     │
               │  (Parse→IR→Gen)   │   │ (to_*_converter.py)  │
               └───────┬───────────┘   └──────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────────┐
    │  Parser  │ │    IR    │ │  Generator   │
    │          │ │          │ │              │
    │ PDF/Image│→│Document  │→│ DOCX / PPTX  │
    │ → Model  │ │  Model   │ │              │
    └──────────┘ └──────────┘ └──────────────┘
```

### 三阶段详解

#### 阶段 1: Parse (`algo/parsers/`)

输入 PDF 或图片，输出 `DocumentModel`。自动选择解析路径：

**数字 PDF 路径**（有嵌入文本层）：
- PyMuPDF 提取文本块 → `TextRun`（保留字体名、字号、粗体、颜色）
- PyMuPDF 提取图片块 → `ImageBlock`（裁剪保存图片字节）
- 几何线条检测 → `TableBlock`（行列结构 + 单元格合并）
- 启发式标题推断（字号 > 1.2× 中位数 → title）
- 阅读顺序计算（单列 top-to-bottom，多列先分列再列内排序）
- 页眉页脚检测（顶部/底部 10% 区域）

**扫描/图片路径**（无文本层或纯图片输入）：
- 优先 PaddleOCR PP-Structure：版面分析 + 表格 + OCR 一步完成
- PaddleOCR 不可用时回退 PyMuPDF 内置 OCR（Tesseract）
- 表格从 PaddleOCR HTML 输出解析为 `TableCell` 结构

#### 阶段 2: DocumentModel IR (`algo/document_model/`)

Pydantic 模型，结构化表示整篇文档：

```
DocumentModel
├── source_path, source_type, needs_ocr, title
└── pages: list[Page]
    └── Page (index, width, height)
        └── blocks: list[LayoutBlock]
            ├── block_type: text|title|list|table|image|formula|header|footer|caption
            ├── bbox: BBox (归一化 [0,1] 坐标)
            ├── reading_order: int
            ├── runs: list[TextRun] (text + font_name + font_size + bold + italic + color)
            ├── table: TableBlock (rows, cols, cells[TableCell])
            ├── image: ImageBlock (image_bytes, fmt)
            └── formula: FormulaBlock (latex)
```

**设计要点**：
- **归一化坐标**：所有 bbox ∈ [0,1]，与页面尺寸解耦。解析不关心输出 DPI，
  生成不关心源格式。
- **阅读顺序一等公民**：每个 block 携带 `reading_order` 索引，
  `page.sorted_blocks` 直接给出正确顺序。
- **多列检测**：`page.has_multiple_columns` 启发式判断，用于 DOCX 分节。

#### 阶段 3: Generate (`algo/generators/`)

消费 `DocumentModel`，输出目标格式：

**DOCX 生成器**（语义重排流）：
- title → `add_heading(level=heading_level)`
- text → `add_paragraph()` + run 级字体/粗体/颜色
- table → `add_table()` + 单元格合并 (`cell.merge()`) + 表头加粗
- image → `add_picture(width=按比例)` + 中文字体回退
- 多列 → OOXML `<w:cols>` 分节
- 阅读顺序 → 文档内容顺序
- 中文字体 → `w:eastAsia` 属性确保 CJK 正确渲染

**PPTX 生成器**（绝对定位画布）：
- 每页 → 一张幻灯片（尺寸 = 源页面 pt × EMU/pt）
- text/title → `add_textbox(left, top, width, height)` 按归一化坐标定位
- table → `add_table()` 定位放置 + 合并单元格
- image → `add_picture(left, top, width, height)` 定位放置
- 字体元数据 → run 级保留（字号、粗体、颜色）
- 公式 → LaTeX 纯文本（可扩展为 OMML）

## 与原有系统的集成

### pipeline.py 改动

`convert()` 函数新增结构化路径判断：
- `target_format ∈ {"docx", "pptx", "html", "markdown"}` → 优先走结构化流水线
- 结构化失败 → 自动回退到原有 `to_{format}_converter`
- 其他格式（xlsx, jpg, png, txt）→ 不受影响，走原路径

这保证了：
1. **零破坏性**：原有转换器完全保留，回退机制确保兼容性
2. **渐进升级**：用户无需改 API 调用方式，自动获得更高质量的 DOCX/PPTX
3. **可观测**：回退时记录 warning 日志

### 文件结构

```
algo/
├── document_model/
│   └── __init__.py          # DocumentModel IR (新增)
├── parsers/
│   └── __init__.py          # DocumentParser (新增)
├── generators/
│   ├── __init__.py          # 生成器导出 (新增)
│   ├── docx_generator.py    # DOCX 生成器 (新增)
│   ├── pptx_generator.py    # PPTX 生成器 (新增)
│   ├── html_generator.py    # HTML 生成器 (新增)
│   └── markdown_generator.py # Markdown 生成器 (新增)
├── converters/              # 原有转换器 (不变，作为 fallback)
├── pipeline.py              # 改动：新增结构化路径 + 回退
└── ...
```

## 测试

`tests/test_structure_pipeline.py` — 29 个测试，覆盖：

- **DocumentModel** (8 tests): BBox 属性、坐标转换、块文本拼接、阅读顺序排序、
  表格单元格查找（含合并）、多列检测
- **Parser** (4 tests): 数字 PDF 解析、表格检测、阅读顺序、图片输入
- **Generator** (11 tests): DOCX 生成（标题/段落/表格/粗体验证）、PPTX 生成、
  HTML 生成（语义标签/run 样式/合并单元格）、Markdown 生成（标题层级/粗体/
  GFM 表格/多页分隔符）
- **Pipeline 端到端** (6 tests): PDF→DOCX、PDF→PPTX、PDF→HTML、PDF→Markdown、
  图片→DOCX、不支持格式报错、文件不存在报错、旧格式兼容

运行：
```bash
PYTHONPATH="algo:backend" python -m pytest tests/test_structure_pipeline.py -v
```

## 未来扩展方向

基于调研中发现的技术趋势，可按优先级扩展：

1. **VLM 增强**：接入 Surya VLM 或 GraniteDocling 作为 advanced 解析层，
   对复杂版面（多列嵌套、跨页表格、手写体）提供更高精度。当前已预留
   `_try_paddle_structure` 作为可替换的解析后端。

2. **公式 OMML 转换**：当前公式以 LaTeX 纯文本保留。可接入 LaTeX→OMML 转换，
   生成 Word 原生公式对象。

3. **跨页表格合并**：当前每页独立检测表格。可参考 Marker 的 `--use_llm` 策略，
   用 LLM 合并跨页表格片段。

4. **LayoutReader 阅读顺序**：当前用几何启发式。可接入 LayoutReader seq2seq 模型
   （ReadingBank 上 98.2% BLEU）提升复杂版面阅读顺序。

5. **字体嵌入**：当前设置字体名但未嵌入字体文件。可提取源 PDF 内嵌字体并
   写入 DOCX (`fontTable.xml`)，确保跨设备渲染一致。

6. **XLSX 生成器**：当前 XLSX 仍走旧转换器路径。可复用 DocumentModel IR 中的
   TableBlock 结构，新增结构化 XLSX 生成器，提升表格转换质量。

7. **TXT 生成器**：当前 TXT 仍走旧转换器路径。可复用 DocumentModel IR 的
   阅读顺序与标题层级，输出结构化纯文本。
