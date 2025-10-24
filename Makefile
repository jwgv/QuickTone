PY=python3
PIP=pip

.ONESHELL:

setup:
	uv sync && uv run pre-commit install

run:
	#uv run uvicorn app.main:app --reload --host $${QT_HOST:-0.0.0.0} --port $${QT_PORT:-8080} --
	uv run uvicorn app.main:app --workers 32  --host $${QT_HOST:-0.0.0.0} --port $${QT_PORT:-8080} --loop uvloop --http httptools
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

