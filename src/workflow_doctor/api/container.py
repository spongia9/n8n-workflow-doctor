"""Container-only network entry; the normal CLI remains loopback-only."""
import os
from pathlib import Path

from .app import create_app
from .config import ApiConfig


def create_container_app():
    # Same-origin Nginx proxy forwards a validated localhost Host. No development
    # cross-origin exception is needed or enabled in the container profile.
    return create_app(ApiConfig(cors_origins=()))


def main():
    if os.environ.get("WORKFLOW_DOCTOR_CONTAINER") != "1" or not Path("/.dockerenv").is_file():
        raise SystemExit("Container entry requires Docker and WORKFLOW_DOCTOR_CONTAINER=1; use the loopback CLI otherwise")
    import uvicorn
    uvicorn.run("workflow_doctor.api.container:create_container_app", factory=True,
                host="0.0.0.0", port=8000, workers=1, access_log=False, proxy_headers=False,
                limit_concurrency=4, backlog=4, timeout_keep_alive=5,
                timeout_graceful_shutdown=20)


if __name__ == "__main__":
    main()
