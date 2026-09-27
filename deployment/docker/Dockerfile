# RIFT Production Dockerfile
# Phase 20: Deployment/Governance - Hardened container

# Frontend build stage: compile the canonical React product UI
# (frontend/) so the production image serves the same application
# that local dev runs, not just the legacy static lab page (web/).
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY frontend/index.html ./
COPY frontend/vite.config.ts frontend/tsconfig.json frontend/tsconfig.node.json ./
COPY frontend/tailwind.config.js frontend/postcss.config.js ./
COPY frontend/public ./public
COPY frontend/src ./src
# Same-origin production: relative /api needs no VITE_API_URL override.
RUN npm run build

# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies, pinned to constraints.txt so the image
# resolves the same versions CI tested (build context must be the repo root).
# src/ must be present: setuptools discovers packages under src/, and the
# install stays editable because api.py resolves web assets relative to the
# installed rift package location (non-editable would point ROOT at
# site-packages/web and 404 the dashboard).
COPY pyproject.toml constraints.txt README.md ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -c constraints.txt -e '.[supabase]'

# Production stage
FROM python:3.11-slim AS production

WORKDIR /app

# Create non-root user
RUN groupadd -r rift && useradd -r -g rift -u 1000 rift

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application
COPY --chown=rift:rift src/ ./src/
COPY --chown=rift:rift backend/ ./backend/
COPY --chown=rift:rift data/ ./data/
COPY --chown=rift:rift web/ ./web/
# Canonical React product UI (built above). The API serves it at /app/
# with SPA fallback; legacy web/ stays at its existing paths.
COPY --chown=rift:rift --from=frontend-builder /build/dist ./frontend-dist/

# Switch to non-root user
USER rift

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health', timeout=3)" || exit 1

# Run server (bind 0.0.0.0: container loopback would be unreachable).
CMD ["python", "-m", "rift.cli", "serve", "--host", "0.0.0.0", "--port", "8080"]