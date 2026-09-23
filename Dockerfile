FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY web ./web
RUN pip install --no-cache-dir . && useradd -m rift && chown -R rift:rift /app
USER rift
EXPOSE 8080
CMD ["python", "-m", "rift.cli", "serve", "--host", "0.0.0.0", "--port", "8080"]
