# 🖥️ Software Development Team — Agent Definitions

## Team Structure

```
      ┌─────────────────────────────────────────┐
      │   🧠 PM Agent (Hunk — Main Session)     │
      │   需求分析 · 任务拆解 · 进度追踪 · 审核   │
      └──────────┬──────────┬──────────┬────────┘
                 │          │          │
     ┌───────────▼──┐ ┌────▼────┐ ┌───▼──────────┐
     │ 🎨 FE Agent  │ │ ⚙️ BE   │ │ 🧪 Algo      │
     │ Frontend     │ │ Backend │ │ Algorithm     │
     │ Engineer     │ │ Engineer│ │ Engineer      │
     └──────────────┘ └─────────┘ └───────────────┘
                 │          │          │
                 └──────────┼──────────┘
                     ┌──────▼──────┐
                     │ 🔧 DevOps   │
                     │ Infra/Deploy│
                     └─────────────┘
```

## Agent Roles

### 🧠 PM Agent (main session — Hunk)
- **Entry point** for all development requests from Arthur
- Breaks requirements into tasks → spawns sub-agents via `sessions_spawn`
- Reviews deliverables, tracks progress, synthesizes outputs
- Has access to the full project context

### 🎨 FE Agent — Frontend Engineer
- **Scope**: Next.js/React UI components, pages, state, styling
- **Outputs**: TSX/TS files, CSS/Tailwind, component code
- **Tasks**: Page routes, component implementation, API integration, responsive design
- **Context**: `/AnyDocConverter/pdf-platform/frontend/`

### ⚙️ BE Agent — Backend Engineer
- **Scope**: FastAPI endpoints, SQLAlchemy models, Celery tasks
- **Outputs**: Python API code, DB schemas, middleware
- **Tasks**: API routing, DB operations, error handling, validation
- **Context**: `/AnyDocConverter/pdf-platform/backend/`

### 🧪 Algo Agent — Algorithm Engineer
- **Scope**: PDF parsing, OCR, format conversion, reconstruction
- **Outputs**: Python processing pipeline code
- **Tasks**: PDF text extraction, image extraction, layout analysis, format conversion
- **Context**: `/AnyDocConverter/pdf-platform/algo/`

### 🔧 DevOps Agent — Infrastructure Engineer
- **Scope**: Docker, CI/CD, nginx, deployment
- **Outputs**: Dockerfiles, compose files, shell scripts, configs
- **Tasks**: Container build optimization, deployment automation, monitoring
- **Context**: `/AnyDocConverter/pdf-platform/infra/`

## Communication Protocol

1. **Arthur → PM Agent**: Requirements via Feishu
2. **PM Agent → Specialist**: Spawn sub-agent with `sessions_spawn()`:
   ```
   - task: clear objective with file paths to modify
   - taskName: stable handle for later targeting
   - toolsAllow: [read, write, edit, exec]
   ```
3. **Specialist → PM Agent**: Sub-agent writes code, completes
4. **PM Agent → Arthur**: Summary of changes, next steps

## Current Project Status

### ✅ Already Complete

**Algo (PDF Processing Engine)** — ~2000+ lines
- `models/` — PDFDocument, ConvertParams (w/ OCR/Layout/Font/Image sub-params)
- `parser/` — PDFParser (PyMuPDF), text extraction, image extraction, layout analysis, font matching
- `ocr/` — OCRManager, PaddleOCR adapter, Tesseract adapter
- `converters/` — All 5 real converters: DOCX (pdf2docx), PPTX (background+overlay), XLSX (table detection), HTML (render+embed), JPG (pdf2image)
- `reconstruct/` — PDF rebuilder, layout/text/image renderers
- `pipeline.py` — Orchestrated conversion entry point

**Backend (FastAPI)** — ~600+ lines
- `core/` — Config (env-based), async database (SQLAlchemy), file storage
- `models/` — File, Task ORM models
- `schemas/` — Request/response Pydantic models
- `api/` — Upload, Convert, Download, Task status, Formats, Params endpoints
- `workers/` — Celery app + async conversion task (wraps algo pipeline)
- `main.py` — FastAPI app with routers + CORS + lifespan

**Frontend (Next.js 14)** — ~1500+ lines
- `src/app/` — Pages: home (upload → format → params → convert), task progress, result download
- `src/components/` — FileUploader, FormatGrid, ParamsPanel (OCR/Layout/Font/Image), ProgressDisplay, PreviewCompare, DownloadCard
- `src/stores/` — Zustand task state management
- `src/lib/` — API client
- `src/types/` — TypeScript type definitions

**Infra** — ~100+ lines
- Docker Compose (postgres, redis, backend, worker, frontend, nginx)
- Dockerfiles (backend, frontend multi-stage, worker)
- Nginx config (API proxy + SPA static serving)
- Deployment script (init.sh)

### ❌ Gaps to Fix

1. **OpenClaw Agent Team** — This document (agent definitions)
2. **`.env` file** — Need to create from `.env.example`
3. **Git repo** — Not initialized
4. **Frontend `next.config.js`** — Need to verify/configure for static export
5. **Alembic migrations** — Not set up (DB uses create_all for now, fine for MVP)
6. **Password mismatch** — docker-compose says `pdfpass` but base config has `postgres`
7. **`to_xlsx_converter.py` logic bug** — Double-call to `page.find_tables()`
8. **Integration test** — Verify end-to-end
