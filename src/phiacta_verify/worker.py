"""Background worker that processes verification jobs from the Redis queue.

The worker uses Redis Streams consumer groups so that multiple worker
instances can share the workload.  Each message is acknowledged only
after the job has been fully processed (or has irrecoverably failed).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from phiacta_verify.comparators import get_comparator
from phiacta_verify.models.enums import JobStatus, VerificationLevel
from phiacta_verify.models.job import VerificationJob
from phiacta_verify.models.result import OutputComparison, VerificationResult
from phiacta_verify.queue import JobQueue
from phiacta_verify.runners import get_runner
from phiacta_verify.sandbox import ContainerSandbox, SecurityPolicy
from phiacta_verify.signing import ResultSigner

logger = logging.getLogger(__name__)

CONSUMER_GROUP = "verify-workers"


async def run_worker(
    queue: JobQueue,
    sandbox: ContainerSandbox,
    signer: ResultSigner,
    consumer_name: str = "worker-1",
) -> None:
    """Long-running coroutine that pulls jobs from the queue and processes them.

    Parameters
    ----------
    queue:
        The Redis-backed job queue.
    sandbox:
        Container sandbox used to execute code.
    signer:
        Ed25519 signer for stamping results.
    consumer_name:
        Unique name for this consumer within the consumer group.
    """
    logger.info("Worker %s starting (group=%s)", consumer_name, CONSUMER_GROUP)

    while True:
        try:
            messages = await queue.dequeue(
                group=CONSUMER_GROUP,
                consumer=consumer_name,
                count=1,
                block_ms=5000,
            )
            if not messages:
                continue

            for msg_id, job in messages:
                try:
                    await process_job(queue, sandbox, signer, job)
                except Exception:
                    logger.exception("Failed to process job %s", job.id)
                    await queue.set_status(str(job.id), JobStatus.FAILED)
                finally:
                    await queue.acknowledge(msg_id, CONSUMER_GROUP)

        except asyncio.CancelledError:
            logger.info("Worker %s shutting down", consumer_name)
            break
        except Exception:
            logger.exception("Worker loop error, retrying in 1 s")
            await asyncio.sleep(1)


async def process_job(
    queue: JobQueue,
    sandbox: ContainerSandbox,
    signer: ResultSigner,
    job: VerificationJob,
) -> None:
    """Execute a single verification job end-to-end.

    1. Mark the job as RUNNING.
    2. Prepare the execution via the appropriate runner.
    3. Run the code inside the container sandbox.
    4. Parse the sandbox output.
    5. Compare outputs against expected values (if any).
    6. Determine the achieved verification level.
    7. Sign the result and store it.
    """
    await queue.set_status(str(job.id), JobStatus.RUNNING)

    # ---- 1. Prepare execution ------------------------------------------------
    runner = get_runner(job.runner_type)
    prepared = runner.prepare(job)

    # ---- 2. Build security policy from job resource limits -------------------
    policy = SecurityPolicy(
        memory_limit_mb=job.resource_limits.memory_mb,
        timeout_seconds=job.resource_limits.timeout_seconds,
        pids_limit=job.resource_limits.pids_limit,
        tmpfs_size_mb=job.resource_limits.disk_mb,
    )

    # ---- 3. Execute in sandbox -----------------------------------------------
    sandbox_result = await sandbox.run(
        image=prepared.image,
        command=prepared.command,
        code_files=prepared.code_files,
        data_files=prepared.data_files,
        policy=policy,
    )

    # ---- 4. Parse output -----------------------------------------------------
    runner_output = runner.parse_output(
        sandbox_result.exit_code,
        sandbox_result.stdout,
        sandbox_result.stderr,
        sandbox_result.output_files,
    )

    # ---- 5. Compare outputs if expected values were provided -----------------
    output_comparisons: list[OutputComparison] = []
    if job.expected_outputs and runner_output.success:
        for expected in job.expected_outputs:
            actual_data = runner_output.outputs.get(expected.name)

            if actual_data is None:
                output_comparisons.append(
                    OutputComparison(
                        name=expected.name,
                        matched=False,
                        method=expected.comparison_method,
                        score=0.0,
                        details={"error": "output not found"},
                    )
                )
                continue

            expected_data = expected.content or b""
            comparator = get_comparator(expected.comparison_method)
            comp_result = comparator.compare(
                expected_data,
                actual_data,
                tolerance=expected.tolerance,
            )

            output_comparisons.append(
                OutputComparison(
                    name=expected.name,
                    matched=comp_result.matched,
                    method=comp_result.method,
                    score=comp_result.score,
                    details=comp_result.details,
                )
            )

    # ---- 6. Determine verification level and pass/fail -----------------------
    if sandbox_result.timed_out:
        level = VerificationLevel.L0_UNVERIFIED
        passed = False
    elif not runner_output.success:
        # Distinguish syntax-only check from total failure.
        if sandbox_result.exit_code != 0:
            level = VerificationLevel.L1_SYNTAX_VERIFIED
        else:
            level = VerificationLevel.L0_UNVERIFIED
        passed = False
    elif output_comparisons and all(c.matched for c in output_comparisons):
        # All expected outputs matched -- use the runner's claimed level.
        level = runner_output.verification_level
        passed = True
    elif output_comparisons:
        # Execution succeeded but some outputs did not match.
        level = VerificationLevel.L2_EXECUTION_VERIFIED
        passed = False
    else:
        # No expected outputs -- rely on the runner's assessment.
        level = runner_output.verification_level
        passed = runner_output.success

    # ---- 7. Build, sign, and store result ------------------------------------
    result = VerificationResult(
        job_id=job.id,
        claim_id=job.claim_id,
        verification_level=level,
        passed=passed,
        code_hash=job.code_hash,
        execution_time_seconds=sandbox_result.execution_time_seconds,
        outputs_matched=output_comparisons or None,
        stdout=sandbox_result.stdout[:1000] if sandbox_result.stdout else None,
        stderr=sandbox_result.stderr[:1000] if sandbox_result.stderr else None,
        error_message=runner_output.errors if not passed else None,
        runner_image=prepared.image,
    )

    result.signature = signer.sign(result)
    await queue.store_result(str(job.id), result)

    logger.info(
        "Job %s completed: level=%s passed=%s time=%.3fs",
        job.id,
        level.value,
        passed,
        sandbox_result.execution_time_seconds,
    )
