.PHONY: install dev-backend dev-frontend dev-algo test clean

# ── 安装依赖 ────────────────────────────────────────────────────────
install: install-backend install-frontend install-algo

install-backend:
	@cd backend && pip install -r requirements.txt 2>/dev/null; \
	pip install pymupdf python-docx openpyxl python-pptx Pillow pdf2image 2>/dev/null
	@echo "✅ Backend dependencies installed"

install-frontend:
	@cd frontend && npm install --silent 2>/dev/null
	@echo "✅ Frontend dependencies installed"

install-algo:
	@pip install -r algo/requirements.txt 2>/dev/null || true
	@echo "✅ Algo dependencies installed"

# ── 本地开发 ─────────────────────────────────────────────────────────
dev-backend:
	@cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	@cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

dev-algo:
	@PYTHONPATH=algo:backend \
	 python3 -c "from algo.pipeline import convert; print('✅ Algo pipeline import OK')"

# ── 测试 ──────────────────────────────────────────────────────────────
test:
	@PYTHONPATH=algo:backend python3 -m pytest tests/ -v $(ARGS)

test-algo:
	@cd algo && python3 -m pytest ../tests/test_pipeline.py -v -k "$(filter-out $@,$(MAKECMDGOALS))" 2>/dev/null || \
	 PYTHONPATH=algo:backend python3 -m pytest tests/test_pipeline.py -v $(ARGS)

# ── 清理 ──────────────────────────────────────────────────────────────
clean:
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleaned"

# ── Docker 部署 ──────────────────────────────────────────────────────
docker-build:
	@cd infra && docker compose build

docker-up:
	@cd infra && docker compose up -d

docker-down:
	@cd infra && docker compose down

# ── Git ────────────────────────────────────────────────────────────────
git-status:
	@git status

git-log:
	@git log --oneline -10
