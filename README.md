# QuickTone

High-performance FastAPI service for real-time and batch sentiment analysis with multiple backends.

## Table of Contents
- [Features](#features)
- [Quick Start](#quick-start)
  - [Native](#native)
  - [UI (React + Vite + Tailwind)](#ui-react--vite--tailwind)
  - [Makefile Helpers](#makefile-helpers)
  - [Docker](#docker)
  - [Docker Compose](#docker-compose)
- [API (v1)](#api-v1)
  - [POST /api/v1/sentiment](#post-apiv1sentiment)
  - [POST /api/v1/sentiment/batch](#post-apiv1sentimentbatch)
  - [POST /api/v1/models/warm](#post-apiv1modelswarm)
  - [GET /api/v1/models/status](#get-apiv1modelsstatus)
  - [GET /health](#get-health)
- [Configuration (Env Vars)](#configuration-env-vars)
  - [Core](#core)
  - [Auth](#auth)
  - [Limits & Performance](#limits--performance)
  - [Caching](#caching)
  - [Models](#models)
  - [Logging](#logging)
- [Auth Usage](#auth-usage)
- [Notes](#notes)
- [Performance (Local Benchmark)](#performance-local-benchmark)
- [Intelligent Caching](#intelligent-caching)
- [Development](#development)
- [CI/CD](#cicd)

## Features
- VADER (default): ultra-fast, zero cold-start, CPU-only
- DistilBERT (optional): higher quality, emotion-aware mapping to sentiment
- DistilBERT-SST-2 (optional): faster, higher quality, emotion-aware mapping to sentiment
- Clean REST endpoints with optional API key auth and simple rate limiting
- Lazy model loading and optional warm-up

## Quick Start

### Native
1. Python 3.11+ recommended (3.13 supported)
2. Create venv and install dependencies
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Run the API
   ```bash
   uvicorn app.main:app --reload --port 8080
   ```
4. Open the docs: http://localhost:8080/docs (or set `QT_PORT`)

### UI (React + Vite + Tailwind)
- Dev: `make ui-dev` (runs Vite on http://localhost:5173, proxies to API)
- Build: `make ui-build` (outputs to `ui/dist`)
- In Docker: UI is built in the image and served at `/` by FastAPI

### Makefile Helpers
- `make setup`
- `make run`
- `make test`
- `make fmt` / `make lint`
- `make build` (Docker)
- `make up` / `make down` (compose)

### Docker
```bash
docker build -t quicktone:dev .
docker run -p 8080:8080 quicktone:dev
```

### Docker Compose
```bash
docker compose up --build
```
- Visit API Docs: http://localhost:8080/docs
- Visit UI: http://localhost:8080/

## API (v1)

### POST /api/v1/sentiment
- Request body
  ```json
  { "text": "I love this!", "model": "vader", "task_type": "sentiment" }
  ```
- Allowed values
  - model: "vader" | "distilbert" | "distilbert-sst-2"
  - task_type: "sentiment" | "emotion"
- Response body
  ```json
  { "model": "string", "sentiment": "positive|negative|neutral", "confidence": 0.0, "processing_time_ms": 0, "task_type": "sentiment|emotion" }
  ```
- Example
  ```bash
  curl -s http://localhost:8080/api/v1/sentiment \
    -H 'Content-Type: application/json' \
    -d '{"text": "I love this!", "model": "vader"}' | jq
  ```

### POST /api/v1/sentiment/batch
- Request body
  ```json
  { "texts": ["I love this!", "This is bad."], "model": "vader", "task_type": "sentiment" }
  ```
- Allowed values
  - model: "vader" | "distilbert" | "distilbert-sst-2"
  - task_type: "sentiment" | "emotion"
- Response body
  ```json
  { "results": [ { "model": "vader", "sentiment": "positive", "confidence": 0.99, "processing_time_ms": 3, "task_type": "sentiment" } ], "total_processing_time_ms": 3, "items_processed": 1 }
  ```

### POST /api/v1/models/warm
Warms the DistilBERT pipeline in the background to reduce first-request latency.

### GET /api/v1/models/status
Returns basic information about loaded models and defaults.

### GET /health
Basic health info including version, default model, and available backends.

## Configuration (Env Vars)

### Core
- `QT_ENV`: `dev|test|prod` (default: `dev`)
- `QT_HOST`: default `0.0.0.0`
- `QT_PORT`: default `8080`
- `QT_MODEL_DEFAULT`: `vader|distilbert|distilbert-sst-2` (default: `vader`)

### Auth
- `QT_AUTH_MODE`: `none|api_key` (default: `none`)
- `QT_API_KEYS`: comma-separated list of valid API keys

### Limits & Performance
- `QT_RATE_LIMIT_ENABLED`: `true|false` (default: `false`)
- `QT_RATE_LIMIT_RPS`: integer (default: `10`)
- `QT_RESPONSE_TIMEOUT_MS`: integer (default: `500`)
- `QT_BATCH_SIZE_LIMIT`: integer (default: `32`)
- `QT_TEXT_LENGTH_LIMIT`: integer (default: `2500`)

### Caching
- `QT_CACHE_BACKEND`: `none|memory` (default: `none`)
- `QT_CACHE_TTL_SECONDS`: integer (default: `3600`)

### Models
- `QT_MODEL_WARM_ON_STARTUP`: `true|false` (default: `true`)
- `QT_DISTILBERT_MODEL`: HF model id (default: `joeddav/distilbert-base-uncased-go-emotions-student`)
- `QT_DISTILBERT_SST_2_MODEL`: HF model id (`distilbert-base-uncased-finetuned-sst-2-english`)
- `QT_GRACEFUL_DEGRADATION`: `true|false` (default: `true`)
- `QT_EMO_SENT_THRESHOLD`: float (default: `0.35`)
- `QT_EMO_SENT_EPSILON`: float (default: `0.05`)

### Logging
- `QT_LOG_LEVEL`: `info|debug|warning|error` (default: `info`)
- `QT_PERFORMANCE_LOGGING`: `true|false` (default: `true`)

## Auth Usage
- Enable API key auth: set `QT_AUTH_MODE=api_key` and `QT_API_KEYS="key1,key2"`.
- Send key in header `X-API-Key: <key>` or `Authorization: Api-Key <key>`.

## Notes
- Default model is VADER for speed. DistilBERT and DistilBERT-SST-2 (faster) are available and can be warmed.
- DistilBERT uses an emotion classification pipeline and maps emotions to binary sentiment using configurable thresholds.
- If DistilBERT fails or times out, QuickTone can gracefully fall back to VADER if enabled.

## Performance (Local Benchmark)
- Model: `distilbert-base-uncased-finetuned-sst-2-english`
- Hardware: MacBook Pro M4 Max (40-core GPU, 128GB RAM)
- Command:
  ```bash
  hey -T "application/json" -m POST -n 50000 -c 1000 \
    -D benchmark/payload-distilbert-sst-2.json \
    http://127.0.0.1:8080/api/v1/sentiment
  ```
- Results: ~**2,200 RPS** for 50,000 requests with 1,000 concurrent connections (no caching)

## Intelligent Caching
QuickTone implements a multi-layered intelligent caching system designed for optimal performance in sentiment analysis workloads.

### Smart Cache Architecture
- Dual-tier design: Separate caches for single requests (2048 entries) and batch operations (256 entries), optimized for different usage patterns
- Context-aware keys: Cache keys include model type, task type, and text content using BLAKE2b hashing to prevent false cache hits across different configurations
- Hybrid eviction: Combines TTL expiration (default 1 hour) with LRU eviction for memory efficiency

### Performance Features
- Zero-overhead when disabled: No caching overhead when `QT_CACHE_BACKEND=none`
- Built-in analytics: Hit/miss ratio tracking for performance monitoring
- Deterministic batch hashing: Stable cache keys for variable-length text batches
- Model-aware separation: Same text cached separately for VADER vs DistilBERT to ensure result accuracy

## Development
- Formatting: black + isort
- Types: mypy (strict)
- Tests: pytest

## CI/CD
- Pre-commit hooks
  - Formatting, linting, type checking, testing
- GitHub Actions
  - CI: Formatting, test, build
  - Deploy: Google Cloud Run via `.github/workflows/deploy-cloudrun.yml`
    - Requires repository Variables or Secrets: `GCP_PROJECT_ID`, `GCP_REGION`, `GAR_REPO`, `CLOUD_RUN_SERVICE`
    - Authentication: either `GCP_SA_KEY` (JSON) or Workload Identity Federation using `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT_EMAIL`
    - See `google-cloud/README.md` for setup details
