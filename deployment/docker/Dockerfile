# RIFT Production Dockerfile
# Phase 20: Deployment/Governance - Hardened container

# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e '.[supabase]'

# Production stage
FROM python:3.11-slim as production

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

# Switch to non-root user
USER rift

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health', timeout=3)" || exit 1

# Run server (bind 0.0.0.0: container loopback would be unreachable).
CMD ["python", "-m", "rift.cli", "serve", "--host", "0.0.0.0", "--port", "8080"]