# 📄 AnyDocConverter — PDF 在线编辑转换平台

基于 Agent 团队协作构建的全栈 PDF 处理平台，支持 PDF → Word/Excel/PPT/HTML/JPG/PNG 格式转换。

## ✨ 功能

- **格式转换** — PDF → DOCX / PPTX / XLSX / HTML / JPG / PNG
- **OCR 增强** — 可选 PaddleOCR / Tesseract，支持多语言
- **版面还原** — 表格检测、图片提取、阅读顺序恢复
- **参数可调** — OCR / 布局 / 图片质量 / 字体匹配
- **异步任务** — Celery + Redis 后台处理，前端实时轮询进度

## 🏗️ 架构

```
Nginx (反向代理)
  ├─ /api/* → FastAPI Backend (Port 8000)
  └─ /*     → Next.js Frontend (Port 3000)

FastAPI Server
  ├─ 文件上传 / 转换任务 / 结果下载 API
  └─ Celery Worker (后台 PDF 处理)

PDF Processing Pipeline
  ├─ 解析器 (PyMuPDF) → 文字/图片/表格 提取
  ├─ OCR 引擎 (PaddleOCR / Tesseract)
  ├─ 转换器 (5+ 种格式)
  └─ 重建器 (ReportLab / WeasyPrint)
```

## 🚀 快速开始

### Docker 部署（推荐）

```bash
cd pdf-platform/infra
./scripts/init.sh
```

或手动：

```bash
cd pdf-platform/infra
docker compose build
docker compose up -d
```

访问: http://localhost

### 本地开发

```bash
cd pdf-platform

# 安装依赖
make install

# 终端 1 — 后端
make dev-backend

# 终端 2 — 前端
make dev-frontend

# 终端 3 — 测试
make test
```

## 🔧 技术栈

| 层 | 技术 | 用途 |
|----|------|------|
| **后端** | FastAPI + SQLAlchemy + Celery | REST API + 异步任务 |
| **前端** | Next.js 14 + React + TailwindCSS | SPA 用户界面 |
| **PDF 解析** | PyMuPDF (fitz) | 文字/图片/表格/布局提取 |
| **OCR** | PaddleOCR / Tesseract | 扫描页文字识别 |
| **转换** | pdf2docx / python-pptx / openpyxl / pdf2image | 格式转换引擎 |
| **重建** | ReportLab / WeasyPrint | 高质量 PDF 重新生成 |
| **存储** | PostgreSQL + Redis + MinIO | 持久化 + 消息队列 |

## 📁 项目结构

```
AnyDocConverter/
├── pdf-platform/
│   ├── algo/                  # PDF 处理引擎
│   │   ├── parser/            # 文字/图片/布局 提取
│   │   ├── ocr/               # OCR 引擎适配器
│   │   ├── converters/        # 格式转换器 (6种)
│   │   ├── reconstruct/       # PDF 重建
│   │   └── utils.py           # 共享工具函数
│   ├── backend/               # FastAPI 服务
│   │   ├── app/api/           # REST 端点
│   │   ├── app/models/        # ORM 模型
│   │   └── workers/           # Celery 任务
│   ├── frontend/              # Next.js SPA
│   │   ├── src/app/           # 页面路由
│   │   ├── src/components/    # UI 组件
│   │   └── src/stores/        # 状态管理
│   ├── infra/                 # 部署配置
│   │   ├── docker-compose.yml
│   │   └── nginx/default.conf
│   └── tests/                 # 集成测试
```

## 👥 Agent 团队

本项目由 6 个 OpenClaw Agent 协作开发：

| Agent | 角色 | 模型 |
|-------|------|------|
| 🦾 **Hunk (main)** | 项目经理 / 协调者 | DeepSeek V4 Flash |
| 🎯 **PM Agent** | 任务拆解 / 进度追踪 | 火山引擎 Ark Code |
| ⚙️ **BE Agent** | 后端开发 (FastAPI) | 火山引擎 Ark Code |
| 🎨 **FE Agent** | 前端开发 (Next.js) | 火山引擎 Ark Code |
| 🧪 **Algo Agent** | 算法引擎 (PDF) | DeepSeek V4 Pro |
| 🔧 **DevOps Agent** | 部署 / Infra | 火山引擎 Ark Code |

编码任务通过 **Claude Code** 执行（Anthropic Claude Sonnet 4），由 PM Agent 拆解并顺序调度。

## 📊 API 文档

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/upload` | 上传 PDF |
| GET | `/api/v1/formats` | 支持的格式列表 |
| GET | `/api/v1/params/{format}` | 格式默认参数 |
| POST | `/api/v1/convert` | 一键转换 |
| GET | `/api/v1/tasks/{id}` | 查询任务状态 |
| POST | `/api/v1/tasks/{id}/start` | 启动已创建的任务 |
| GET | `/api/v1/download/{id}` | 下载结果 |

API 文档 (Swagger): http://localhost:8000/docs (Docker 部署后)

## 📦 支持格式

| 格式 | 输入 | 输出 | 质量 |
|------|------|------|------|
| DOCX | ✅ | ✅ | 可编辑 Word，保留字体/图片 |
| PPTX | ✅ | ✅ | 背景图+文字 overlay |
| XLSX | ✅ | ✅ | 表格检测+文本 fallback |
| HTML | ✅ | ✅ | 嵌入式 base64 图片 |
| JPG | ✅ | ✅ | 可调 DPI/质量 |
| PNG | ✅ | ✅ | 无损输出 |
| TXT | ❌ | ✅ | 纯文本提取 |
| Markdown | ❌ | ✅ | 简单文本 |

## 📝 License

MIT
