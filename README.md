QuickTone - Real-Time Sentiment Analysis API

QuickTone is a high-performance FastAPI service providing real-time and batch sentiment analysis with multiple backends:
- VADER (default): ultra-fast, zero cold-start, CPU-only
- DistilBERT (optional): higher quality, emotion-aware mapping to sentiment
- DistilBERT-SST-2 (optional): faster, higher quality, emotion-aware mapping to sentiment

The service exposes clean REST endpoints, optional API key auth, simple rate limiting, lazy model loading, and model warm-up.

Quick start
- Native
  1) Python 3.11+ recommended (3.13 supported)
  2) Create venv and install deps
     - python -m venv .venv && source .venv/bin/activate
     - pip install -r requirements.txt
  3) Run the API
     - uvicorn app.main:app --reload
  4) Open http://localhost:8080/docs (or set QT_PORT)

- UI (React + Vite + Tailwind)
  - Dev: make ui-dev (runs Vite on http://localhost:5173, proxies to API)
  - Build: make ui-build (outputs to ui/dist)
  - In Docker: UI is built in the image and served at /ui by FastAPI

- Makefile helpers
  - make setup
  - make run
  - make test
  - make fmt / make lint
  - make build (Docker)
  - make up / make down (compose)

- Docker
  - docker build -t quicktone:dev .
  - docker run -p 8080:8080 quicktone:dev

- Docker Compose
  - docker compose up --build
  - Visit API Docs: http://localhost:8080/docs
  - Visit UI: http://localhost:8080/ui

Endpoints (v1)
- POST /api/v1/sentiment
  Request: { "text": str, "model"?: "vader"|"distilbert"|"distilbert-sst-2", "task_type"?: "sentiment"|"emotion" }
  Response: { model, sentiment, confidence, processing_time_ms, task_type }

  Example:
  curl -s http://localhost:8080/api/v1/sentiment \
    -H 'Content-Type: application/json' \
    -d '{"text": "I love this!", "model": "vader"}' | jq

- POST /api/v1/sentiment/batch
  Request: { "texts": list[str], "model"?: "vader"|"distilbert"|"distilbert-sst-2"", "task_type"?: "sentiment"|"emotion" }
  Response: { results: list[SentimentResponse], total_processing_time_ms, items_processed }

- POST /api/v1/models/warm
  Warms the DistilBERT pipeline in the background to reduce first-request latency.

- GET /api/v1/models/status
  Returns basic information about loaded models and defaults.

- GET /health
  Basic health info including version, default model, and available backends.

Configuration (env vars)
- Core
  - QT_ENV: dev|test|prod (default: dev)
  - QT_HOST: default 0.0.0.0
  - QT_PORT: default 8080
  - QT_MODEL_DEFAULT: vader|distilbert|distilbert-sst-2 (default: vader)

- Auth
  - QT_AUTH_MODE: none|api_key (default: none)
  - QT_API_KEYS: comma-separated list of valid API keys

- Limits & Performance
  - QT_RATE_LIMIT_ENABLED: true|false (default: false)
  - QT_RATE_LIMIT_RPS: integer (default: 10)
  - QT_RESPONSE_TIMEOUT_MS: integer (default: 500)
  - QT_BATCH_SIZE_LIMIT: integer (default: 32)
  - QT_TEXT_LENGTH_LIMIT: integer (default: 2500)

- Caching
  - QT_CACHE_BACKEND: none|memory (default: none)
  - QT_CACHE_TTL_SECONDS: integer (default: 3600)

- Models
  - QT_MODEL_WARM_ON_STARTUP: true|false (default: true)
  - QT_DISTILBERT_MODEL: HF model id (default: joeddav/distilbert-base-uncased-go-emotions-student)
  - QT_DISTILBERT_SST_2_MODEL: HF model id (distilbert-base-uncased-finetuned-sst-2-english)
  - QT_GRACEFUL_DEGRADATION: true|false (default: true)
  - QT_EMO_SENT_THRESHOLD: float (default: 0.35)
  - QT_EMO_SENT_EPSILON: float (default: 0.05)

- Logging
  - QT_LOG_LEVEL: info|debug|warning|error (default: info)
  - QT_PERFORMANCE_LOGGING: true|false (default: true)

Auth usage
- To enable API key auth, set QT_AUTH_MODE=api_key and QT_API_KEYS="key1,key2".
- Send key in header X-API-Key: <key> or Authorization: Api-Key <key>.

Notes
- Default model is VADER for speed. DistilBERT and DistilBERT-SST-2 (faster) are available and warmed optionally.
- DistilBERT uses an emotion classification pipeline and maps emotions → binary sentiment using configurable thresholds.
- If DistilBERT fails or times out, QuickTone can gracefully fall back to VADER if enabled.

Development
- Formatting: black + isort
- Types: mypy (strict)
- Tests: pytest

CI/CD
- Pre-commit hooks 
  - Formatting, linting, type checking, testing
- GitHub Actions 
  - CI: Formatting, test, build
