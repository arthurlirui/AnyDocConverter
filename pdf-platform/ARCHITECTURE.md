# 📄 PDF 在线编辑转换平台 — 技术方案设计

## 1. 项目概述

构建一个全栈 PDF 在线处理平台，对标 iLovePDF，支持：
- PDF 内容解析与结构分析
- PDF → Word / PPT / Excel / HTML / JPG 格式转换
- 可编辑文档输出（非图片嵌入）
- 照片级 PDF 重建
- 用户可调参数（OCR、布局、图片质量、字体匹配）

---

## 2. 技术选型

### 2.1 后端 — Python (FastAPI)

| 库 | 用途 | 选型理由 |
|---|---|---|
| **PyMuPDF (fitz)** | PDF 解析（文字、字体、图片、布局） | 速度极快，解析完整，支持文本/图片/矢量提取 |
| **pdf2docx** | PDF → DOCX 核心转换 | 基于 PyMuPDF，布局还原度好 |
| **python-docx** | DOCX 创建/编辑 | 成熟的 Word 文档操作库 |
| **python-pptx** | PPTX 创建/编辑 | 支持文字、图片、表格布局 |
| **openpyxl** | XLSX 创建/编辑 | 成熟的 Excel 文档操作库 |
| **Pillow** | 图片处理 | 支持格式转换、DPI/压缩/色彩空间调整 |
| **pdf2image** | PDF → 图片（JPG/PNG） | 基于 Poppler，页面栅格化 |
| **ReportLab** | PDF 重建/生成 | 精确控制 PDF 布局、字体嵌入 |
| **WeasyPrint** | HTML → PDF | CSS 渲染引擎，用于高质量 PDF 重建 |
| **PaddleOCR** | OCR 文字识别 | 中文支持优于 Tesseract，可区分语言 |
| **Celery + Redis** | 任务队列 | 异步 PDF 处理，进度跟踪 |
| **FastAPI** | Web 框架 | 异步、高性能、自动 OpenAPI 文档 |

### 2.2 系统工具依赖

| 工具 | 用途 |
|---|---|
| **LibreOffice (headless)** | 文档格式互转（WORD→PDF, PPT→PDF 等） |
| **GhostScript** | PDF 压缩、修复、PostScript 处理 |
| **Poppler (pdftoppm)** | PDF 转图片（高保真） |
| **Tesseract OCR** | OCR 备选引擎 |

### 2.3 前端 — React + Next.js

| 库 | 用途 |
|---|---|
| **Next.js 14** | 前端框架（App Router） |
| **Tailwind CSS** | 样式系统 |
| **react-dropzone** | 拖拽上传 |
| **shadcn/ui** | UI 组件库 |
| **react-pdf** | PDF 在线预览 |
| **Immer** | 参数面板状态管理 |
| **Socket.IO Client** | 实时进度推送 |
| **Zustand** | 轻量状态管理 |

### 2.4 存储 & 中间件

| 组件 | 用途 |
|---|---|
| **Redis** | 任务队列 Broker + 结果缓存 |
| **MinIO** | 文件存储（S3 兼容） |
| **PostgreSQL** | 用户/任务/配置持久化 |

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                         Nginx / Caddy                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │   Next.js App    │  ← 前端 (Port 3000)
              │  (SSR + SPA + WS)│
              └────────┬────────┘
                       │ HTTP/WS
              ┌────────▼────────┐
              │  FastAPI Server  │  ← 后端 API (Port 8000)
              │  REST + WebSocket│
              └────────┬────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
  ┌──────▼──────┐ ┌───▼────┐ ┌─────▼──────┐
  │  Celery     │ │ Redis  │ │ PostgreSQL │
  │  Workers    │ │ (Queue │ │ (Users,     │
  │  (PDF       │ │ + Cache│ │  Tasks,     │
  │   Processing)│ │  + WS) │ │  Configs)   │
  └──────┬──────┘ └────────┘ └────────────┘
         │
    ┌────▼──────────────────────────────┐
    │        PDF Processing Pipeline      │
    │  ┌─────────┐ ┌──────────┐ ┌─────┐  │
    │  │ Parser  │→│ Converter │→│Export│  │
    │  │ PyMuPDF │ │ pdf2docx │ │DOCX │  │
    │  │ Paddle  │ │ reportlab│ │PPTX │  │
    │  │ OCR     │ │ WeasyPrint│ │XLSX │  │
    │  └─────────┘ └──────────┘ └─────┘  │
    │  + LibreOffice / Pandoc fallback    │
    └─────────────────────────────────────┘
```

---

## 4. 模块划分

### 4.1 Backend 模块 (be-agent)

```
backend/
├── app/
│   ├── api/              # FastAPI 路由
│   │   ├── upload.py      # 文件上传端点
│   │   ├── convert.py     # 转换任务 API
│   │   ├── download.py    # 结果下载
│   │   └── progress.py    # WebSocket 进度推送
│   ├── models/           # SQLAlchemy 模型
│   │   ├── task.py        # 任务状态模型
│   │   └── file.py        # 文件元数据模型
│   ├── core/
│   │   ├── config.py      # 配置管理
│   │   └── storage.py     # 文件存储抽象 (本地/MinIO)
│   └── celery_app.py     # Celery 配置
├── workers/              # Celery 任务定义
│   ├── parse.py          # 解析任务
│   ├── convert.py        # 转换任务
│   └── compress.py       # 压缩任务
└── requirements.txt
```

### 4.2 Algorithm 模块 (algo-agent)

```
algo/
├── parser/               # PDF 解析引擎
│   ├── text_extractor.py # 文字提取 (位置/字体/样式)
│   ├── image_extractor.py# 图片提取 (DPI/色彩空间)
│   ├── layout_analyzer.py# 版面分析 (段落/表格/列)
│   └── font_matcher.py   # 字体匹配与替换
├── ocr/                  # OCR 引擎
│   ├── paddle_ocr.py     # PaddleOCR 封装
│   ├── tesseract_ocr.py  # Tesseract 封装
│   └── ocr_manager.py    # OCR 引擎管理/切换
├── converters/           # 格式转换器
│   ├── to_docx.py        # PDF → DOCX
│   ├── to_pptx.py        # PDF → PPTX
│   ├── to_xlsx.py        # PDF → XLSX
│   ├── to_html.py        # PDF → HTML
│   └── to_jpg.py         # PDF → JPG
├── reconstruct/          # PDF 重建引擎
│   ├── pdf_rebuilder.py  # PDF 重建编排
│   ├── layout_renderer.py# 布局渲染
│   ├── text_renderer.py  # 文字渲染 (字体匹配)
│   └── image_processor.py# 图片优化
├── models/               # 数据模型
│   ├── pdf_document.py   # PDF 文档结构模型
│   ├── page.py           # 页面模型
│   └── block.py          # 内容块模型 (text/image/table)
└── utils/
    ├── image_utils.py    # 图片工具函数
    └── font_utils.py     # 字体工具函数
```

### 4.3 Frontend 模块 (fe-agent)

```
frontend/
├── src/
│   ├── app/              # Next.js App Router
│   │   ├── page.tsx       # 首页 - 拖拽上传
│   │   ├── convert/       # 转换页面
│   │   ├── preview/       # 预览对比页面
│   │   └── history/       # 历史记录
│   ├── components/
│   │   ├── upload/        # 上传组件 (DropZone)
│   │   ├── params/        # 参数面板
│   │   │   ├── OCROptions.tsx
│   │   │   ├── LayoutOptions.tsx
│   │   │   ├── ImageQualityOptions.tsx
│   │   │   └── FontOptions.tsx
│   │   ├── preview/       # 预览对比组件
│   │   │   ├── PDFViewer.tsx
│   │   │   └── SideBySide.tsx
│   │   ├── progress/      # 进度组件
│   │   └── common/        # 通用组件
│   ├── lib/               # 工具函数 + API 客户端
│   ├── stores/            # Zustand stores
│   └── types/             # TypeScript 类型定义
├── public/
│   └── uploads/           # 上传文件
└── package.json
```

### 4.4 DevOps 模块 (devops-agent)

```
infra/
├── docker-compose.yml     # 服务编排
├── Dockerfile.backend     # 后端镜像
├── Dockerfile.frontend    # 前端镜像
├── Dockerfile.worker      # Celery Worker 镜像
├── nginx/
│   └── default.conf       # 反向代理配置
└── scripts/
    └── init.sh            # 初始化脚本 (安装系统依赖)
```

---

## 5. 核心流程

### 5.1 PDF → Word 转换流程（典型场景）

```
用户上传 PDF
     │
     ▼
1. PDF 解析 (PyMuPDF)
   ├── 提取文字块 (位置、字体、大小、颜色)
   ├── 提取图片 (DPI、格式、嵌入位置)
   ├── 提取表格 (行列坐标)
   └── 提取布局结构 (页面尺寸、边距、列)
     │
     ▼
2. [可选] OCR 增强 (PaddleOCR)
   ├── 扫描页 OCR 识别
   └── 文字层对齐/替换
     │
     ▼
3. 布局重建 (Layout Analyzer)
   ├── 段落合并 (基于行距/缩进)
   ├── 表格识别 (基于坐标)
   ├── 阅读顺序排序 (从左到右、从上到下)
   └── 样式推断 (标题/正文/列表)
     │
     ▼
4. DOCX 生成 (python-docx)
   ├── 段落 + 字体样式
   ├── 图片嵌入 + 位置
   ├── 表格创建
   └── 页眉页脚(可选)
     │
     ▼
5. 后处理优化
   ├── 格式校验
   └── 文件大小优化
     │
     ▼
用户下载
```

### 5.2 照片级 PDF 重建流程

```
用户输入 (编辑后的 DOCX / 参数)
     │
     ▼
1. 文档解析 (python-docx 解析)
   ├── 全部文字内容 + 样式
   ├── 所有图片 (提取原始分辨率)
   └── 布局信息 (段落、表格、位置)
     │
     ▼
2. 参数应用
   ├── 图片质量 → DPI / 压缩 / 色彩空间
   ├── 字体匹配 → 精确/近似/替换
   └── 布局精度 → 精确绝对定位 / 自适应流式
     │
     ▼
3. PDF 渲染 (ReportLab / WeasyPrint)
   ├── 高 DPI 栅格化 (300-600 DPI)
   ├── 字体嵌入 (PDF/A 标准)
   ├── 图片无损/有损优化
   └── 元数据保留 (书签、超链接)
     │
     ▼
4. 后处理 (GhostScript)
   ├── PDF 压缩
   ├── PDF/A 合规检查
   └── 质量验证
     │
     ▼
用户下载
```

---

## 6. API 设计

```
POST   /api/v1/upload              # 上传文件
GET    /api/v1/tasks/:id           # 获取任务状态
POST   /api/v1/tasks/:id/start     # 启动转换任务
GET    /api/v1/tasks/:id/result    # 获取转换结果
WS     /ws/tasks/:id/progress      # 实时进度推送
GET    /api/v1/download/:file_id   # 下载结果文件
GET    /api/v1/formats             # 支持的格式列表
GET    /api/v1/params/:format      # 获取格式的默认参数
POST   /api/v1/preview             # 参数预览 (快速)
```

### 转换请求体

```json
{
  "file_id": "uuid",
  "target_format": "docx",
  "params": {
    "ocr": {
      "enabled": true,
      "engine": "paddle",
      "languages": ["zh", "en"]
    },
    "layout": {
      "preservation": "exact",
      "detect_tables": true,
      "detect_lists": true
    },
    "image": {
      "dpi": 300,
      "compression": "jpeg",
      "quality": 95,
      "color_space": "rgb"
    },
    "font": {
      "mode": "approximate",
      "fallback_font": "NotoSansCJK"
    }
  }
}
```

---

## 7. 目录结构（完整）

```
/home/pz04-a-001/.openclaw/workspace/AnyDocConverter/pdf-platform/
├── ARCHITECTURE.md        ← 本文档
├── docker-compose.yml     ← DevOps
├── Dockerfile.*           ← DevOps
├── nginx/                 ← DevOps
├── backend/               ← BE
│   ├── app/
│   ├── workers/
│   ├── requirements.txt
│   └── Dockerfile
├── algo/                  ← Algo
│   ├── parser/
│   ├── ocr/
│   ├── converters/
│   ├── reconstruct/
│   └── requirements.txt
├── frontend/              ← FE
│   ├── src/
│   ├── package.json
│   └── Dockerfile
└── shared/                ← 共享
    ├── models/             # Pydantic 模型 (BE ↔ Algo)
    └── tests/              # 集成测试
```

---

## 8. 开发顺序

### Phase 1: 核心管道 (MVP)
1. ✅ PDF 解析引擎 (PyMuPDF) — Algo
2. ✅ 文件上传 + 任务队列 — BE
3. ✅ PDF → DOCX 转换 — Algo
4. ✅ 结果下载 API — BE
5. ✅ 前端上传 + 下载界面 — FE
6. ✅ Docker Compose 基础部署 — DevOps

### Phase 2: 格式扩展
7. PDF → PPTX / XLSX / HTML / JPG — Algo
8. OCR 集成 (PaddleOCR) — Algo
9. 参数面板前端 — FE
10. 参数透传 API — BE

### Phase 3: 高级功能
11. 照片级 PDF 重建 — Algo
12. 实时进度 WebSocket — BE + FE
13. 预览对比组件 — FE
14. 性能优化 + 缓存 — BE + DevOps

---

## 9. 约束 & 注意事项

- **PyMuPDF 许可证**: AGPL — 商用需注意；仅后端服务调用不触发复制限制
- **LibreOffice**: 使用 `--headless` 模式，需安装完整包 (~800MB)
- **PaddleOCR**: GPU 加速需要 CUDA。Docker 部署使用 CPU 版即可
- **文件大小限制**: 初始设为 50MB，队列处理，不做同步
- **安全性**: 上传文件沙箱处理，防止恶意 PDF 脚本
