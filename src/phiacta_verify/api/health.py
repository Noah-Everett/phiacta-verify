"""Health and readiness probes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe -- always returns OK if the process is running."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """Readiness probe -- checks that Redis is reachable.

    Returns HTTP 200 with ``{"status": "ready"}`` when the queue backend
    is healthy, or HTTP 503 with ``{"status": "not_ready"}`` otherwise.
    """
    queue = getattr(request.app.state, "queue", None)
    if queue is not None and await queue.health_check():
        return JSONResponse(content={"status": "ready"}, status_code=200)
    return JSONResponse(content={"status": "not_ready"}, status_code=503)
