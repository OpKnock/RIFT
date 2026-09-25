# RIFT demo Dockerfile (simple single-stage build for local try-out).
# For production use deployment/docker/Dockerfile (multi-stage, pinned
# dependencies, healthcheck). Build context must be the repo root.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml constraints.txt README.md ./
COPY src ./src
COPY web ./web
# Editable install: api.py resolves web assets relative to the installed
# rift package location, so a non-editable install would 404 the dashboard.
RUN pip install --no-cache-dir -c constraints.txt -e . && useradd -m rift && chown -R rift:rift /app
USER rift
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health', timeout=3)" || exit 1
CMD ["python", "-m", "rift.cli", "serve", "--host", "0.0.0.0", "--port", "8080"]
