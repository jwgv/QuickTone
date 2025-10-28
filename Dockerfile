# syntax=docker/dockerfile:1

# --- UI build stage ---
FROM node:20-alpine AS ui-build
WORKDIR /ui
COPY ui/package.json ui/package-lock.json* ./
RUN npm ci || npm i
COPY ui/ ./
RUN npm run build

# --- Python base image ---
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps (for transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy application
COPY app ./app
COPY main.py ./
COPY README.md pyproject.toml ./

# Copy built UI assets
COPY --from=ui-build /ui/dist ./static/ui

ENV QT_HOST=0.0.0.0 \
    QT_PORT=8080 \
    QT_MODEL_DEFAULT=vader \
    QT_MODEL_WARM_ON_STARTUP=true

EXPOSE 8080

#CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
# Use the main.py script which reads PORT env var dynamically
CMD ["python", "main.py"]
