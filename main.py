import os

import uvicorn

# Expose the ASGI app from app.main for compatibility
from app.main import app  # noqa: F401


def get_port() -> int:
    # Default port is 8080; can be overridden by QT_PORT env var
    val = os.getenv("QT_PORT", "8080")
    try:
        return int(val)
    except ValueError:
        return 8080


def get_host() -> str:
    return os.getenv("QT_HOST", "0.0.0.0")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=get_host(), port=get_port(), reload=True)
