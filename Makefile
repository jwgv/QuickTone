PY=python3
PIP=pip

.ONESHELL:

.PHONY: setup run benchmark ui-install ui-dev ui-build fmt lint test build up down

setup:
	uv sync && uv run pre-commit install

run:
	QT_CACHE_BACKEND=memory \
	QT_TORCH_DEVICE=auto \
	QT_RESPONSE_TIMEOUT_MS=5000 \
	QT_GRACEFUL_DEGRADATION=true \
	QT_BATCH_SIZE_LIMIT=32 \
	QT_CACHE_TTL_SECONDS=1800 \
	PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0 \
	uv run uvicorn app.main:app \
		--workers $${QT_UV_WORKERS:-4} \
		--host $${QT_HOST:-0.0.0.0} \
		--port $${QT_PORT:-8080} \
		--loop uvloop \
		--http httptools \
		#--limit-concurrency $${QT_UV_CC_LIMIT:-1100}

benchmark:
	DATE=$$(date +%Y%m%d_%H%M%S); \
	OUT_FILE=benchmark/benchmark_sentiment_$${DATE}.txt; \
	QT_CACHE_BACKEND=none \
	QT_TORCH_DEVICE=auto \
	QT_RESPONSE_TIMEOUT_MS=5000 \
	QT_GRACEFUL_DEGRADATION=true \
	QT_BATCH_SIZE_LIMIT=32 \
	QT_CACHE_TTL_SECONDS=1800 \
	PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0 \
	uv run uvicorn app.main:app \
		--workers 16 \
		--host $${QT_HOST:-0.0.0.0} \
		--port $${QT_PORT:-8080} \
		--loop uvloop \
		--http httptools & \
	SERVER_PID=$$!; \
	trap 'kill $$SERVER_PID 2>/dev/null || true' EXIT; \
	echo "Sleeping for 15 seconds while the workers spin up. Standby..." ; \
	sleep 15; \
	echo "Running hey benchmark, output -> $$OUT_FILE"; \
	hey -T "application/json" -m POST -n 50000 -c 1000 \
		-D benchmark/payload-distilbert-sst-2.json \
		http://127.0.0.1:8080/api/v1/sentiment > $$OUT_FILE

ui-install:
	cd ui && (npm ci || npm i)

ui-dev:
	cd ui && (npm ci || npm i) && npm run dev

ui-build:
	cd ui && (npm ci || npm i) && npm run build

fmt:
	uv run black . && uv run isort .

lint:
	uv run black --check . && uv run isort --check-only . # && uv run mypy .

test:
	uv run pytest -q

build:
	docker build -t quicktone:dev .

up:
	docker compose up --build

down:
	docker compose down -v

