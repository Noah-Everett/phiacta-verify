"""Route aggregation -- combines all API sub-routers into a single router."""

from fastapi import APIRouter

from phiacta_verify.api.health import router as health_router
from phiacta_verify.api.jobs import router as jobs_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(jobs_router)
