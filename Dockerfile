# ============================================================
# Klikk AI Portal — Multi-stage Docker Build
# Stage 1: Build Vue.js frontend
# Stage 2: Python backend + serve static files
# ============================================================

# --- Stage 1: Build Vue.js frontend ---
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python backend ---
FROM python:3.12-slim

LABEL maintainer="Klikk Group" \
      description="Klikk AI Portal — Vue.js + FastAPI TM1 Planning Agent"

RUN apt-get update \
    && apt-get install -y --no-install-recommends --fix-missing \
        build-essential \
        libpq-dev \
        curl \
    || (apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl) \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./

# Agent skill modules (overlay commit 77665bcc; avoids empty host bind mount on ./mcp_server/skills).
COPY mcp_overlay/backend/mcp_server/ ./mcp_server/

# Copy MCP server (canonical TM1 + PG tool implementations)
COPY mcp_tm1_server/ ./mcp_tm1_server/

# Copy built Vue.js frontend
COPY --from=frontend-build /app/frontend/dist ./static

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
