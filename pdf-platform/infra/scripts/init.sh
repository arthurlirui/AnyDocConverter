#!/usr/bin/env bash
# ============================================================
# PDF Platform — One-Click Deployment Script
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$INFRA_DIR")"

cd "$INFRA_DIR"

echo "========================================"
echo "  📄 PDF Platform — Deployment Script"
echo "========================================"
echo ""

# --------------------------------------------------
# Step 1: Prerequisite check
# --------------------------------------------------
echo "🔍 Checking prerequisites..."

# Check Docker
if ! command -v docker &>/dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check Docker Compose
if ! docker compose version &>/dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker Compose plugin."
    exit 1
fi

echo "   ✅ Docker: $(docker --version)"
echo "   ✅ Docker Compose: $(docker compose version --short)"
echo ""

# --------------------------------------------------
# Step 2: Port conflict check
# --------------------------------------------------
echo "🔍 Checking for port conflicts..."

check_port() {
    local port=$1
    local service=$2
    if ss -tlnp "sport = :$port" 2>/dev/null | grep -q ":$port"; then
        echo "   ⚠️  Port $port is already in use! ($service will use this port)"
        echo "      Please stop the existing service or change the port mapping."
        return 1
    fi
}

PORT_OK=true
check_port 80 "Nginx (frontend portal)" || PORT_OK=false
check_port 5432 "PostgreSQL" || PORT_OK=false
check_port 6379 "Redis" || PORT_OK=false
check_port 8000 "Backend API" || PORT_OK=false

if [ "$PORT_OK" = false ]; then
    echo ""
    echo "❌ Port conflict detected. Please free the ports listed above and try again."
    exit 1
fi
echo "   ✅ All required ports are available."
echo ""

# --------------------------------------------------
# Step 3: Create required directories
# --------------------------------------------------
echo "📁 Ensuring volume directories..."
mkdir -p "${PROJECT_DIR}/uploads" "${PROJECT_DIR}/converted"
echo "   ✅ Uploads & conversion directories ready."
echo ""

# --------------------------------------------------
# Step 4: Build images
# --------------------------------------------------
echo "🏗️  Building Docker images..."
echo "    (This may take several minutes on first run)"
echo ""
docker compose build --pull
echo ""

# --------------------------------------------------
# Step 5: Start services
# --------------------------------------------------
echo "🚀 Starting services..."
echo ""
docker compose up -d
echo ""

# --------------------------------------------------
# Step 6: Wait for services to be healthy
# --------------------------------------------------
echo "⏳ Waiting for services to become healthy..."
echo "    (Backend may take a moment for DB migrations)"

# Wait for backend to respond
RETRIES=30
for i in $(seq 1 $RETRIES); do
    if curl -sf http://localhost:8000/docs >/dev/null 2>&1; then
        echo "   ✅ Backend API is ready (http://localhost:8000)"
        break
    fi
    if [ "$i" -eq "$RETRIES" ]; then
        echo "   ⚠️  Backend didn't respond within ${RETRIES}s — check 'docker compose logs backend'"
    else
        sleep 1
    fi
done

# --------------------------------------------------
# Done
# --------------------------------------------------
echo ""
echo "========================================"
echo "  ✅ PDF Platform is now running!"
echo "========================================"
echo ""
echo "  Platform:     http://localhost"
echo "  API Docs:     http://localhost:8000/docs  (backend direct; not exposed via nginx)"
echo "  PostgreSQL:   localhost:5432 (pdfuser / pdfpass)"
echo "  Redis:        localhost:6379"
echo ""
echo "  Useful commands:"
echo "    docker compose ps           # List services"
echo "    docker compose logs -f      # Follow all logs"
echo "    docker compose logs backend # Backend logs"
echo "    docker compose down         # Stop all services"
echo "    docker compose down -v      # Stop + remove volumes"
echo ""
echo "========================================"
