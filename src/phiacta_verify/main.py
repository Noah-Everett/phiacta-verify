"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="phiacta-verify",
    description="Sandboxed verification engine for scientific claims.",
    version="0.1.0",
)
