# AnyDocConverter — PDF / Image Conversion Platform

A full-stack platform for converting PDFs and images to **DOCX / PPTX / XLSX / HTML / JPG / PNG / Markdown / TXT**, with built-in OCR (PaddleOCR / Tesseract) for scanned documents, photos, and screenshots.

Built with a multi-agent workflow (6 OpenClaw agents + Claude Code for coding tasks). See [ARCHITECTURE.md](ARCHITECTURE.md) for the team topology.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)

---

## Table of contents

- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Quick start (Docker)](#quick-start-docker)
- [Local development](#local-development)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Supported formats](#supported-formats)
- [Conversion parameters](#conversion-parameters)
- [Adding a new converter](#adding-a-new-converter)
- [Testing](#testing)
- [Tech stack](#tech-stack)
- [Known limitations](#known-limitations)
- [License](#license)

---

## Architecture

```
                       ┌──────────────────────────┐
                       │   Nginx reverse proxy :80 │
                       └────────────┬─────────────┘
                          /api/* ┌──┴──┐ /*
                                 ▼     ▼
               ┌────────────────┐  ┌────────────────┐
               │ FastAPI :8000  │  │ Next.js :3000  │
               │  REST API      │  │  SPA frontend  │
               └───────┬────────┘  └────────────────┘
                       │ Celery task
                       ▼
               ┌────────────────┐         ┌──────────────┐
               │ Celery Worker  │ ──OCR──▶│ PaddleOCR    │
               │ conversion     │         │ / Tesseract  │
               └───────┬────────┘         └──────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
   ┌──────────┐  ┌──────────┐  ┌──────────────┐
   │PostgreSQL│  │  Redis   │  │ Local files  │
   │ metadata │  │  broker  │  │ uploads/     │
   └──────────┘  └──────────┘  └──────────────┘
```

**Request flow:**

1. Frontend uploads the source file → `POST /api/v1/upload` → returns `file_id`.
2. Frontend calls `POST /api/v1/convert` with `file_id` + `target_format` + `params`.
3. Backend creates a `Task` row, commits it, then dispatches `perform_conversion.delay(...)` to Celery.
4. Worker picks the task off the `conversions` queue, runs the algo pipeline, writes the result to `uploads/`, and updates the `Task` row.
5. Frontend polls `GET /api/v1/tasks/{id}` until `status` is `completed` or `failed`.
6. Frontend downloads via `GET /api/v1/download/{task_id}`.

**Conversion pipeline** (`algo/pipeline.py`):

```
input detection → converter dispatch → (per-converter OCR / layout) → result path
```

- Image inputs (or OCR-enabled runs) skip PDF pre-parsing and route directly to OCR-capable converters.
- Each converter is a stateless module-level function with signature `(file_path, params, output_dir) -> str`.
- On exception, the pipeline cleans up any temp directory it created.

> The `algo/parser/` and `algo/reconstruct/` packages exist as scaffolding for a future layout-reconstruction path but are **not currently wired into the pipeline** — each converter calls `fitz.open` directly. See [Known limitations](#known-limitations).

---

## Repository layout

```
AnyDocConverter/
├── pdf-platform/
│   ├── algo/                       # Core PDF processing engine
│   │   ├── pipeline.py             # Conversion pipeline entry point
│   │   ├── utils.py                # Format ↔ extension / MIME mappings
│   │   ├── models/
│   │   │   ├── params.py           # ConvertParams param model
│   │   │   └── pdf_document.py     # PDFDocument / Page data models
│   │   ├── parser/                 # PyMuPDF parsing (text/image/layout) — not yet wired in
│   │   ├── reconstruct/            # Layout reconstruction — not yet wired in
│   │   ├── ocr/                    # OCR engine adapters
│   │   │   ├── ocr_manager.py      # Engine dispatch (paddle / tesseract)
│   │   │   ├── paddle_ocr_adapter.py
│   │   │   ├── tesseract_ocr_adapter.py
│   │   │   └── ocr_text.py         # Image / PDF → plain text
│   │   └── converters/             # 8 format converters
│   │       ├── __init__.py         # Exports + converter contract docs
│   │       ├── base_converter.py   # Abstract base class
│   │       └── to_{format}_converter.py
│   ├── backend/                    # FastAPI service
│   │   ├── app/
│   │   │   ├── api/                # REST endpoints (upload/convert/task/download/formats/params)
│   │   │   ├── core/               # Database / config / storage
│   │   │   ├── models/             # SQLAlchemy ORM (Task, File)
│   │   │   └── schemas/            # Pydantic request / response models
│   │   └── workers/                # Celery app + tasks
│   ├── frontend/                   # Next.js SPA
│   │   └── src/
│   │       ├── app/                # Routes (upload / convert / result)
│   │       ├── components/         # UI components (params / progress / download)
│   │       ├── stores/             # Zustand state
│   │       ├── lib/                # API client
│   │       └── types/              # Backend-aligned TypeScript types
│   ├── infra/                      # Deployment config
│   │   ├── docker-compose.yml
│   │   ├── Dockerfile.{backend,worker,frontend}
│   │   ├── nginx/default.conf
│   │   └── scripts/init.sh
│   ├── tests/                      # Integration / UI tests
│   ├── Makefile                    # Dev command shortcuts
│   └── dev.sh                      # Local dev bootstrap script
├── ARCHITECTURE.md                 # Multi-agent team architecture
├── OCR_DEPLOYMENT.md               # PaddleOCR deployment guide
├── SERVER_DEPLOYMENT.md            # Server deployment guide
└── README.md
```

---

## Quick start (Docker)

The fastest path to a running stack. Requires Docker + the Compose plugin.

```bash
cd pdf-platform/infra
./scripts/init.sh          # one-shot: build + start + wait for health
# or manually:
# docker compose build && docker compose up -d
```

Once healthy:

| Service     | URL / port                         | Notes                                   |
|-------------|------------------------------------|-----------------------------------------|
| Platform UI | http://localhost                   | Nginx entry point                       |
| API docs    | http://localhost:8000/docs         | Swagger (backend direct; not via nginx) |
| FastAPI     | 8000                               | REST API                                |
| Next.js     | 3000 (container-internal)          | SPA, proxied by nginx                   |
| PostgreSQL  | 5432 (pdfuser / pdfpass)           | Metadata only                           |
| Redis       | 6379                               | Celery broker / result backend          |

> **First run downloads PaddleOCR models** (~100 MB) on the first conversion that uses OCR. Subsequent runs use the `paddle_models` named volume to cache them.

---

## Local development

Recommended for working on a single layer (frontend / backend / algo) without rebuilding Docker images.

### Prerequisites

- Python 3.12
- Node.js 20+ and npm
- Redis (optional — only needed for the async `/convert` path; `/convert/sync` works without it)
- System packages: `poppler` (for `pdf2image`), `tesseract-ocr` + `tesseract-ocr-chi-sim` (for the Tesseract OCR path)

### Bootstrap

```bash
cd pdf-platform
./dev.sh                 # guided setup: venv, deps, .env, frontend install
```

`dev.sh` creates a `.venv/`, installs backend + algo + frontend deps, and copies `.env.example` to `.env` if missing. It detects Windows (Git Bash) venvs automatically.

### Run the services

Three terminals:

```bash
# Terminal 1 — backend API
cd pdf-platform
source .venv/bin/activate          # Windows: .venv/Scripts/activate
cd backend && python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd pdf-platform/frontend
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

# Terminal 3 — Celery worker (only if Redis is running)
cd pdf-platform
source .venv/bin/activate
PYTHONPATH="$(pwd)/algo:$(pwd)/backend" \
  celery -A workers.celery:celery_app worker \
  -Q conversions,pdf-platform-default --loglevel=info --concurrency=2
```

> **Without Redis**, skip Terminal 3 and have the frontend call `/api/v1/convert/sync` instead of `/api/v1/convert`. The sync endpoint runs the conversion in-process and returns the result directly.

### Makefile shortcuts

```bash
make install           # install backend + frontend + algo deps
make dev-backend       # uvicorn --reload
make dev-frontend      # npm run dev with NEXT_PUBLIC_API_URL set
make dev-algo          # smoke-test that algo.pipeline imports cleanly
make test              # run pytest against tests/
make test-algo         # run only tests/test_pipeline.py
make docker-build      # build Docker images
make docker-up         # docker compose up -d
make docker-down       # docker compose down
make clean             # remove __pycache__ / .pytest_cache / *.pyc
```

---

## Configuration

All backend config is read from environment variables via `app.core.config.Settings` (Pydantic Settings). Defaults are sane for local dev.

| Variable             | Default                                   | Description                                        |
|----------------------|-------------------------------------------|----------------------------------------------------|
| `DATABASE_URL`       | `sqlite+aiosqlite:///./pdfplatform.db`    | SQLAlchemy async URL. Use `postgresql+asyncpg://…` in Docker. |
| `REDIS_URL`          | `redis://localhost:6379/0`                | Celery broker + result backend (derived).          |
| `UPLOAD_DIR`         | `./data/uploads` (dev) / `/app/uploads` (Docker) | Where source + result files are stored.      |
| `MAX_UPLOAD_SIZE_MB` | 50                                        | Max upload size. **Note:** not currently enforced server-side — see [Known limitations](#known-limitations). |
| `CORS_ORIGINS`       | `http://localhost:3000`                   | Comma-separated allowed origins.                   |

Docker-compose also sets `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`, but these are ignored — the app derives both from `REDIS_URL`.

Frontend config is a single build-time variable:

| Variable             | Default | Description                                                                |
|----------------------|---------|----------------------------------------------------------------------------|
| `NEXT_PUBLIC_API_URL`| `""`    | Backend base URL. Empty in Docker (nginx proxies `/api/*`); `http://localhost:8000` in dev. |

---

## API reference

All endpoints are prefixed with `/api/v1`.

| Method | Path                  | Description                                            |
|--------|-----------------------|--------------------------------------------------------|
| POST   | `/upload`             | Upload a PDF / image; returns `file_id`                |
| GET    | `/formats`            | List supported target formats                          |
| GET    | `/params/{format}`    | Default conversion params for a format                 |
| POST   | `/convert`            | One-shot upload → convert (async, via Celery)          |
| POST   | `/convert/sync`       | Synchronous conversion (no Celery; local dev)          |
| GET    | `/tasks/{id}`         | Poll task status / progress / result                   |
| POST   | `/tasks/{id}/start`   | Start (or restart) an existing task with new params    |
| GET    | `/download/{file_id}` | Download result (`file_id` accepts a Task id too)      |

### Typical flow

```bash
# 1. Upload
curl -F "file=@sample.pdf" http://localhost:8000/api/v1/upload
# → { "file_id": "uuid", "filename": "sample.pdf", "size": 12345 }

# 2. Convert (async)
curl -X POST http://localhost:8000/api/v1/convert \
  -H "Content-Type: application/json" \
  -d '{"file_id":"<uuid>","target_format":"docx","params":{}}'
# → { "id": "task-uuid", "status": "queued", ... }

# 3. Poll until completed
curl http://localhost:8000/api/v1/tasks/<task-uuid>
# → { "status": "completed", "progress": 1.0,
#     "result": {"file_id":"task-uuid","filename":"converted_abc12345.docx","path":"…"} }

# 4. Download (pass the task id)
curl -OJ http://localhost:8000/api/v1/download/<task-uuid>
```

### `TaskResponse.result` shape

Consistent across all endpoints that return `TaskResponse`:

- `null` while the task is queued / processing / failed, or has no result file.
- `{ "file_id": <task id>, "filename": <result filename>, "path": <storage relative path> }` when `status === "completed"`.

> `result.file_id` is the **task** id (the handle `/download/{id}` accepts), not the source File id. This is intentional — see `backend/app/api/download.py`.

---

## Supported formats

| Format     | Inputs        | Output  | Notes                                                       |
|------------|---------------|---------|-------------------------------------------------------------|
| **DOCX**   | PDF / image   | `.docx` | Editable Word; OCR mode emits text paragraphs               |
| **PPTX**   | PDF           | `.pptx` | Per-page background image + editable text overlay           |
| **XLSX**   | PDF           | `.xlsx` | Table detection; pages without tables fall back to text     |
| **HTML**   | PDF / image   | `.html` | Layout restoration + base64-embedded images                 |
| **JPG**    | PDF           | `.jpg`  | One image per page; DPI / quality adjustable                |
| **PNG**    | PDF           | `.png`  | One image per page; lossless                                |
| **Markdown**| PDF / image  | `.md`   | Heading levels inferred from font size                      |
| **TXT**    | PDF / image   | `.txt`  | Plain text extraction with page separators                  |

> Multi-page outputs (JPG / PNG) return an output **directory** path; single-page outputs return a file path. The worker handles both.

> The `GET /formats` endpoint also advertises a `pdf-edit` entry. This is **not yet implemented** by the algo pipeline — selecting it will fail at conversion time. See [Known limitations](#known-limitations).

---

## Conversion parameters

Defined in `algo/models/params.py` and mirrored in `backend/app/schemas/task.py`. The two must stay structurally identical so the backend can pass params straight through to the pipeline.

```python
ConvertParams:
  ocr:        # enabled, engine ("paddle"|"tesseract"), language,
              # min_confidence, enhance_image, enhance_mode ("standard"|"hard"),
              # upscale_factor, contrast, sharpness, binarize
  layout:     # detect_tables, detect_images,
              # detect_headers_footers, reading_order
  image:      # quality, max_width, max_height, dpi
  font:       # fallback_font, embed_fonts, preserve_size
  output_format, start_page (0-indexed), end_page (inclusive, None = last)
```

Per-format defaults are served by `GET /api/v1/params/{format}`; the frontend loads them automatically when the user picks a format.

---

## Adding a new converter

The converter contract is documented in `algo/converters/__init__.py`. Steps:

1. **Implement the converter** at `algo/converters/to_{format}_converter.py` with a module-level function:
   ```python
   def convert(file_path: str, params: ConvertParams, output_dir: str) -> str:
       """Return the output file path (or output dir for multi-page outputs)."""
   ```
2. **Export it** from `algo/converters/__init__.py` as `convert_to_{format}`.
3. **Register it** in the `_FORMAT_MAP` dict in `algo/pipeline.py`.
4. **Add the format id** to `CONVERTER_FORMATS` in `algo/utils.py` (this is what `GET /formats` and validation use).
5. **Add format metadata** to `_KNOWN_FORMATS` in `backend/app/api/formats.py` (id, name, icon, description, target_ext, mime_type).
6. **Add per-format default params** in `_FORMAT_PARAMS` in `backend/app/api/params.py` if the format needs non-default settings.
7. **Add a test** in `tests/test_pipeline.py` parametrized over the new format.

Stateless module-level functions (no class instantiation) are the established convention — match it.

---

## Testing

```bash
# All tests
make test

# Algo pipeline only (format round-trip tests)
make test-algo

# UI smoke / e2e (requires services running + Playwright)
py -m pytest tests/test_ui_e2e.py -v
py -m pytest tests/ui_smoke_test.py -v
```

The algo pipeline test (`tests/test_pipeline.py`) is the canonical regression suite — it parametrizes over every supported format and asserts the converter produces a non-empty output. Run it after any change to `algo/`.

UI tests require the full stack to be running (backend + frontend + worker) and Playwright browsers installed (`py -m playwright install`). They also depend on `examples/*.pdf` fixtures — see [Known limitations](#known-limitations).

---

## Tech stack

| Layer            | Tech                                                   | Purpose                              |
|------------------|--------------------------------------------------------|--------------------------------------|
| **Backend API**  | FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2         | REST API, param validation           |
| **Async tasks**  | Celery + Redis                                         | Background PDF processing            |
| **Frontend**     | Next.js 14 + React + TypeScript + TailwindCSS + Zustand | SPA UI                               |
| **PDF parsing**  | PyMuPDF (fitz)                                         | Text / image / table extraction      |
| **OCR**          | PaddleOCR (default) / Tesseract                        | Scanned-page / image text recognition|
| **Format output**| pdf2docx / python-pptx / openpyxl / pdf2image          | DOCX / PPTX / XLSX / JPG / PNG       |
| **Storage**      | PostgreSQL (metadata) + local filesystem (files)       | Persistence                          |
| **Deployment**   | Docker Compose + Nginx                                 | Container orchestration + reverse proxy |

---

## Known limitations

These are tracked from the most recent code review. The critical blockers (broken Celery queue routing, race condition on task dispatch, missing `pdf2docx`/`aiosqlite` deps, broken Dockerfile paths) have been fixed; the items below remain.

- **`pdf-edit` format is advertised but not implemented.** `GET /formats` lists it, but the algo pipeline has no converter for it. Selecting it fails at conversion time. Either implement the converter or remove the entry from `_KNOWN_FORMATS`.
- **`algo/parser/` and `algo/reconstruct/` are dead code.** They were scaffolded for a layout-reconstruction path but are not wired into the pipeline. Each converter calls `fitz.open` directly. Either wire them in or remove them.
- **`pytesseract` is commented out in `algo/requirements.txt`.** The Tesseract adapter is referenced by `ocr_manager.py`, but the pip package isn't installed. Setting `ocr.engine="tesseract"` will raise `ImportError` at adapter construction. Uncomment the line to enable the Tesseract path.
- **`MAX_UPLOAD_SIZE_MB` is not enforced.** The setting exists but no endpoint checks it; uploads are read entirely into memory. Nginx caps at 100 MB, the backend at 50 MB (unenforced) — uploads between 50–100 MB pass nginx then may exhaust backend memory.
- **No file cleanup on task failure / deletion.** `storage.delete_file` exists but is never called; orphaned files accumulate in `uploads/`.
- **`examples/*.pdf` test fixtures are not committed.** `tests/test_ui_e2e.py` depends on them but they're untracked, so the e2e test fails on a fresh clone. Either commit small fixtures or generate them in-test like `ui_smoke_test.py` does.
- **`Task.status` has no DB-level enum constraint.** It's a free-form `String(16)`; typos in status strings would silently persist.
- **No foreign key from `Task.file_id` to `File.id`.** A task can reference a non-existent file; deleting a file orphans its task rows.
- **No authentication on any endpoint.** The platform is open by default; add auth before any public deployment.

---

## License

MIT
