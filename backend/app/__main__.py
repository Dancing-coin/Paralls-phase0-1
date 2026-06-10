from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("PHASE0_BACKEND_HOST", "127.0.0.1")
    port = int(os.environ.get("PHASE0_BACKEND_PORT", "8000"))
    log_level = os.environ.get("PHASE0_BACKEND_LOG_LEVEL", "info")
    reload_mode = os.environ.get("PHASE0_BACKEND_RELOAD", "").lower() in {"1", "true", "yes", "on"}

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=reload_mode,
    )


if __name__ == "__main__":
    main()
