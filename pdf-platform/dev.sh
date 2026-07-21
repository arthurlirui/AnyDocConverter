#!/usr/bin/env bash
# ============================================================
# PDF Platform — Local Development Quick Start
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================"
echo "  PDF Platform — Local Dev Setup"
echo "========================================"

# ── 1. Prerequisites ─────────────────────────────────
echo ""
echo "[1/5] Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || { echo "❌ python3 required"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ node required"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "❌ npm required"; exit 1; }
command -v redis-server >/dev/null 2>&1 && REDIS_AVAIL=true || REDIS_AVAIL=false

echo "   ✅ python3: $(python3 --version)"
echo "   ✅ node: $(node --version)"
echo "   ✅ npm: $(npm --version)"
if $REDIS_AVAIL; then echo "   ✅ redis-server available"; else echo "   ⚠️ redis not installed (Celery won't work)"; fi

# ── 2. Python virtual env ────────────────────────────
echo ""
echo "[2/5] Setting up Python virtual environment..."

# SCRIPT_DIR is already the pdf-platform project root (the directory
# containing this script), so the venv lives at $SCRIPT_DIR/.venv — not
# $SCRIPT_DIR/pdf-platform/.venv (that doubled path never exists).
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    python3 -m venv "$SCRIPT_DIR/.venv"
    echo "   ✅ Virtual environment created"
else
    echo "   ✅ Virtual environment exists"
fi

# Activate the venv using the OS-correct activate script.
if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/.venv/bin/activate"
elif [ -f "$SCRIPT_DIR/.venv/Scripts/activate" ]; then
    # Windows (Git Bash / MSYS) venv layout
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/.venv/Scripts/activate"
else
    echo "❌ Could not find venv activate script"
    exit 1
fi

pip install -q --upgrade pip
echo "   Installing backend dependencies..."
pip install -q -r "$SCRIPT_DIR/backend/requirements.txt"
echo "   Installing algo dependencies..."
pip install -q -r "$SCRIPT_DIR/algo/requirements.txt"

# Install additional PDF processing libs (pdf2docx is required by the DOCX converter)
pip install -q pymupdf python-docx openpyxl python-pptx Pillow pdf2image pdf2docx pdfplumber

echo "   ✅ Python dependencies installed"

# ── 3. Frontend dependencies ─────────────────────────
echo ""
echo "[3/5] Installing frontend dependencies..."

cd "$SCRIPT_DIR/frontend"
npm install --silent 2>/dev/null
echo "   ✅ Frontend dependencies installed"

# ── 4. Environment ───────────────────────────────────
echo ""
echo "[4/5] Configuring environment..."

if [ ! -f "$SCRIPT_DIR/backend/.env" ]; then
    cp "$SCRIPT_DIR/backend/.env.example" "$SCRIPT_DIR/backend/.env"
    echo "   ✅ Created .env from .env.example"
    echo "   ⚠️ Edit .env to set your DATABASE_URL and REDIS_URL"
else
    echo "   ✅ .env already exists"
fi

# ── 5. Done ──────────────────────────────────────────
echo ""
echo "[5/5] Setup complete!"
echo ""
echo "========================================"
echo "  🚀 Quick Start Commands"
echo "========================================"
echo ""
echo "  Terminal 1 — Backend API:"
echo "    cd $SCRIPT_DIR"
echo "    source .venv/bin/activate   # (Windows: .venv/Scripts/activate)"
echo "    cd backend && python -m uvicorn app.main:app --reload --port 8000"
echo ""
echo "  Terminal 2 — Frontend (dev mode):"
echo "    cd $SCRIPT_DIR/frontend"
echo "    NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev"
echo ""
echo "  Terminal 3 — Celery Worker (optional):"
echo "    cd $SCRIPT_DIR"
echo "    source .venv/bin/activate   # (Windows: .venv/Scripts/activate)"
echo "    PYTHONPATH=$SCRIPT_DIR/algo:$SCRIPT_DIR/backend \\"
echo "      celery -A workers.celery:celery_app worker -Q conversions,pdf-platform-default --loglevel=info --concurrency=2"
echo ""
echo "  Open: http://localhost:3000"
echo ""
