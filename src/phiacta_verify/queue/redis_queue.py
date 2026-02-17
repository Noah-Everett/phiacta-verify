"""Job queue via Redis Streams.

Provides :class:`JobQueue` -- the primary interface for enqueuing,
dequeuing, and tracking verification jobs backed by Redis Streams and
plain key-value storage for status and results.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

import redis.asyncio as redis

from phiacta_verify.models.enums import JobStatus
from phiacta_verify.models.job import VerificationJob
from phiacta_verify.models.result import VerificationResult

logger = logging.getLogger(__name__)

# Redis key prefixes / names
STREAM_KEY = "verify:jobs:stream"
STATUS_PREFIX = "verify:jobs:status:"
RESULT_PREFIX = "verify:jobs:result:"
JOB_PREFIX = "verify:jobs:data:"
JOBS_INDEX_KEY = "verify:jobs:index"


class JobQueue:
    """Redis-backed job queue using Redis Streams.

    Parameters
    ----------
    redis_client:
        An ``redis.asyncio.Redis`` instance connected to the Redis server.
    """

    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Return ``True`` if Redis is reachable."""
        try:
            return await self._redis.ping()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Enqueue / Dequeue
    # ------------------------------------------------------------------

    async def enqueue(self, job: VerificationJob) -> str:
        """Add a job to the stream and set its status to QUEUED.

        Returns the Redis message ID.
        """
        job_id = str(job.id)
        job_data = job.model_dump_json()

        # Store the full job data for later retrieval.
        await self._redis.set(f"{JOB_PREFIX}{job_id}", job_data)

        # Track job ID in the index (sorted set, scored by timestamp).
        await self._redis.zadd(
            JOBS_INDEX_KEY,
            {job_id: job.created_at.timestamp()},
        )

        # Publish to the stream.
        msg_id: bytes = await self._redis.xadd(
            STREAM_KEY,
            {"job_id": job_id, "data": job_data},
        )

        await self.set_status(job_id, JobStatus.QUEUED)
        logger.info("Enqueued job %s (msg_id=%s)", job_id, msg_id)
        return msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)

    async def dequeue(
        self,
        group: str,
        consumer: str,
        count: int = 1,
        block_ms: int = 5000,
    ) -> list[tuple[str, VerificationJob]]:
        """Read new messages from the stream as part of a consumer group.

        Automatically creates the consumer group if it does not yet exist.

        Returns a list of ``(message_id, VerificationJob)`` tuples.
        """
        # Ensure the consumer group exists.
        try:
            await self._redis.xgroup_create(
                STREAM_KEY, group, id="0", mkstream=True
            )
        except redis.ResponseError as exc:
            # "BUSYGROUP Consumer Group name already exists"
            if "BUSYGROUP" not in str(exc):
                raise

        raw: list = await self._redis.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={STREAM_KEY: ">"},
            count=count,
            block=block_ms,
        )

        results: list[tuple[str, VerificationJob]] = []
        if not raw:
            return results

        for _stream_name, messages in raw:
            for msg_id, fields in messages:
                msg_id_str = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
                try:
                    data_str = fields[b"data"] if b"data" in fields else fields.get("data", b"")
                    if isinstance(data_str, bytes):
                        data_str = data_str.decode()
                    job = VerificationJob.model_validate_json(data_str)
                    results.append((msg_id_str, job))
                except Exception:
                    logger.exception("Failed to deserialise job from message %s", msg_id_str)

        return results

    async def acknowledge(self, msg_id: str, group: str) -> None:
        """Acknowledge a message so it is not re-delivered."""
        await self._redis.xack(STREAM_KEY, group, msg_id)

    # ------------------------------------------------------------------
    # Status tracking
    # ------------------------------------------------------------------

    async def set_status(self, job_id: str, status: JobStatus) -> None:
        """Update the status of a job."""
        await self._redis.set(f"{STATUS_PREFIX}{job_id}", status.value)
        logger.debug("Job %s -> %s", job_id, status.value)

    async def get_status(self, job_id: str) -> JobStatus | None:
        """Retrieve the current status of a job, or ``None`` if unknown."""
        raw = await self._redis.get(f"{STATUS_PREFIX}{job_id}")
        if raw is None:
            return None
        value = raw.decode() if isinstance(raw, bytes) else raw
        try:
            return JobStatus(value)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Result storage
    # ------------------------------------------------------------------

    async def store_result(self, job_id: str, result: VerificationResult) -> None:
        """Persist a verification result and mark the job as COMPLETED."""
        await self._redis.set(
            f"{RESULT_PREFIX}{job_id}",
            result.model_dump_json(),
        )
        await self.set_status(job_id, JobStatus.COMPLETED)

    async def get_result(self, job_id: str) -> VerificationResult | None:
        """Retrieve a stored verification result, or ``None``."""
        raw = await self._redis.get(f"{RESULT_PREFIX}{job_id}")
        if raw is None:
            return None
        data = raw.decode() if isinstance(raw, bytes) else raw
        return VerificationResult.model_validate_json(data)

    # ------------------------------------------------------------------
    # Job data retrieval
    # ------------------------------------------------------------------

    async def get_job(self, job_id: str) -> VerificationJob | None:
        """Retrieve the full job data, or ``None``."""
        raw = await self._redis.get(f"{JOB_PREFIX}{job_id}")
        if raw is None:
            return None
        data = raw.decode() if isinstance(raw, bytes) else raw
        return VerificationJob.model_validate_json(data)

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    async def list_recent_jobs(self, limit: int = 50) -> list[dict]:
        """Return the most recent *limit* job IDs with their statuses.

        Returns a list of dicts with ``job_id`` and ``status`` keys,
        ordered by creation time (newest first).
        """
        # Use the sorted-set index (descending by score = timestamp).
        job_ids_raw: list = await self._redis.zrevrange(
            JOBS_INDEX_KEY, 0, limit - 1
        )

        results: list[dict] = []
        for raw_id in job_ids_raw:
            job_id = raw_id.decode() if isinstance(raw_id, bytes) else raw_id
            status = await self.get_status(job_id)
            results.append({
                "job_id": job_id,
                "status": status.value if status else "UNKNOWN",
            })

        return results

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying Redis connection."""
        await self._redis.aclose()
