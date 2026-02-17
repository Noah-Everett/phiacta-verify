"""FastAPI application entry point.

Creates the app with a lifespan that initialises Redis, the job queue,
the result signer, the container sandbox, the phiacta backend client,
and a background worker task.  Everything is stored in ``app.state``
and torn down cleanly on shutdown.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from phiacta_verify.api.router import api_router
from phiacta_verify.config import Settings
from phiacta_verify.phiacta_client import PhiactaClient
from phiacta_verify.queue import JobQueue
from phiacta_verify.sandbox import ContainerSandbox
from phiacta_verify.signing import ResultSigner
from phiacta_verify.worker import run_worker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan -- set up and tear down shared resources.

    On startup:
        1. Load :class:`Settings` from the environment.
        2. Connect to Redis.
        3. Create :class:`JobQueue`, :class:`ResultSigner`,
           :class:`ContainerSandbox`, and :class:`PhiactaClient`.
        4. Start a background worker coroutine.
        5. Store all objects in ``app.state``.

    On shutdown:
        1. Cancel the background worker.
        2. Close the phiacta client.
        3. Close the Redis connection.
    """
    settings = Settings()

    # Configure root logging level.
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger.info("Starting phiacta-verify (log_level=%s)", settings.log_level)

    # ---- Redis -----------------------------------------------------------
    redis_client = aioredis.from_url(
        settings.redis_url,
        decode_responses=False,
    )
    queue = JobQueue(redis_client)

    # ---- Signer ----------------------------------------------------------
    signer = ResultSigner(private_key_path=settings.signing_key_path)

    # ---- Sandbox ---------------------------------------------------------
    sandbox = ContainerSandbox()

    # ---- Phiacta client --------------------------------------------------
    phiacta_client = PhiactaClient(
        base_url=settings.phiacta_api_url,
        api_key=settings.phiacta_api_key,
    )

    # ---- Store in app.state ----------------------------------------------
    app.state.settings = settings
    app.state.queue = queue
    app.state.signer = signer
    app.state.sandbox = sandbox
    app.state.phiacta_client = phiacta_client

    # ---- Background worker -----------------------------------------------
    worker_task = asyncio.create_task(
        run_worker(
            queue=queue,
            sandbox=sandbox,
            signer=signer,
            phiacta_client=phiacta_client,
        ),
        name="verification-worker",
    )

    logger.info("Application startup complete")

    try:
        yield
    finally:
        # ---- Shutdown ----------------------------------------------------
        logger.info("Shutting down phiacta-verify")

        # Cancel the worker and wait for it to finish.
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Close the phiacta client.
        await phiacta_client.close()

        # Close the Redis connection.
        await queue.close()

        logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="phiacta-verify",
    description="Sandboxed verification engine for scientific claims.",
    version="0.1.0",
    lifespan=lifespan,
)

# ---- Middleware ----------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=Settings().cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ---- Routes --------------------------------------------------------------

app.include_router(api_router)
