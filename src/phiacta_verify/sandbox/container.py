"""Docker container lifecycle management for sandboxed code execution."""

from __future__ import annotations

import asyncio
import io
import logging
import re
import tarfile
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import docker
import docker.errors
import requests.exceptions

from phiacta_verify.sandbox.security import SecurityPolicy

logger = logging.getLogger(__name__)

# Docker images that the sandbox is allowed to run.  Any image not in this
# set is rejected before a container is ever created.
_ALLOWED_IMAGES: frozenset[str] = frozenset({
    "phiacta-verify-runner-python:latest",
    "phiacta-verify-runner-r:latest",
    "phiacta-verify-runner-julia:latest",
    "phiacta-verify-runner-lean4:latest",
    "phiacta-verify-runner-symbolic:latest",
})

# Maximum bytes of stdout/stderr captured from the container.
_MAX_OUTPUT_BYTES: int = 64 * 1024  # 64 KB

# Regex to strip ANSI escape sequences (colours, cursor movement, etc.).
_ANSI_ESCAPE_RE: re.Pattern[str] = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# Control characters to strip (everything except newline \n, carriage return \r, tab \t).
_CONTROL_CHAR_RE: re.Pattern[str] = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Environment variable names that must never be forwarded to sandbox
# containers because they can alter interpreter behaviour in dangerous ways
# (e.g. executing arbitrary code at startup, loading shared libraries).
_BLOCKED_ENV_VARS: frozenset[str] = frozenset({
    "LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONSTARTUP", "PYTHONPATH",
    "PYTHONINSPECT", "PYTHONBREAKPOINT", "RUBYOPT", "PERL5OPT",
    "NODE_OPTIONS", "JAVA_TOOL_OPTIONS", "R_PROFILE", "R_PROFILE_USER",
    "R_ENVIRON", "R_ENVIRON_USER", "JULIA_LOAD_PATH", "JULIA_DEPOT_PATH",
    "BASH_ENV", "ENV", "CDPATH", "GLOBIGNORE", "PATH", "HOME",
})

# Maximum total bytes of output files collected from /output/.
_MAX_OUTPUT_FILES_BYTES: int = 32 * 1024 * 1024  # 32 MB


def _sanitize_output(raw: str) -> str:
    """Strip ANSI escape codes and control characters from container output.

    Newlines, carriage returns, and tabs are preserved because they carry
    meaningful formatting for program output.
    """
    text = _ANSI_ESCAPE_RE.sub("", raw)
    text = _CONTROL_CHAR_RE.sub("", text)
    return text


def _truncate_bytes(data: bytes, limit: int = _MAX_OUTPUT_BYTES) -> bytes:
    """Truncate *data* to at most *limit* bytes.

    If the data is truncated, a trailing marker is appended so downstream
    consumers know the output was cut short.
    """
    if len(data) <= limit:
        return data
    return data[:limit] + b"\n... [truncated at 64 KB]\n"


def _make_tar(files: dict[str, str | bytes]) -> bytes:
    """Create an in-memory tar archive from a mapping of path -> content.

    String values are UTF-8 encoded.  The returned bytes can be passed
    directly to ``container.put_archive``.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, content in files.items():
            raw = content.encode("utf-8") if isinstance(content, str) else content
            info = tarfile.TarInfo(name=name)
            info.size = len(raw)
            # Readable by the container user (typically root or a non-root runner).
            info.mode = 0o444
            tar.addfile(info, io.BytesIO(raw))
    buf.seek(0)
    return buf.read()


def _extract_tar(data: bytes) -> dict[str, bytes]:
    """Extract an in-memory tar archive into a dict of path -> content.

    Rejects members with absolute paths or path-traversal components
    (``..``) to prevent a malicious container from crafting archives that
    would reference files outside the expected directory.
    """
    result: dict[str, bytes] = {}
    buf = io.BytesIO(data)
    with tarfile.open(fileobj=buf, mode="r") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            # Reject path traversal and absolute paths.
            if member.name.startswith("/") or ".." in member.name.split("/"):
                logger.warning(
                    "Skipping tar member with suspicious path: %s", member.name
                )
                continue
            extracted = tar.extractfile(member)
            if extracted is not None:
                result[member.name] = extracted.read()
    return result


@dataclass(frozen=True)
class SandboxResult:
    """Outcome of a sandboxed container execution."""

    exit_code: int
    stdout: str
    stderr: str
    output_files: dict[str, bytes] = field(default_factory=dict)
    execution_time_seconds: float = 0.0
    timed_out: bool = False


class ContainerSandbox:
    """Manages the full lifecycle of an ephemeral Docker container.

    Each call to :meth:`run` creates a fresh container, executes the
    specified command, collects results, and **unconditionally** removes the
    container regardless of success or failure.

    All blocking Docker SDK calls are dispatched via
    ``asyncio.to_thread`` so that the event loop is never blocked.
    """

    def __init__(self, docker_client: docker.DockerClient | None = None) -> None:
        self._client = docker_client or docker.from_env()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        image: str,
        command: list[str],
        code_files: dict[str, str],
        data_files: dict[str, bytes] | None = None,
        policy: SecurityPolicy | None = None,
        env_vars: dict[str, str] | None = None,
    ) -> SandboxResult:
        """Execute *command* inside a sandboxed container and return the result.

        Parameters
        ----------
        image:
            Docker image to use (must already be pulled).
        command:
            Command and arguments to execute inside the container.
        code_files:
            Mapping of ``relative_path -> source_code`` that will be placed
            under ``/code/`` inside the container (read-only bind mount).
        data_files:
            Optional mapping of ``relative_path -> raw_bytes`` that will be
            placed under ``/data/`` inside the container (read-only bind
            mount).  Pass ``None`` if no data files are needed.
        policy:
            Security policy governing resource limits.  Defaults to a
            fresh ``SecurityPolicy()`` with all defaults.
        env_vars:
            Optional environment variables to set inside the container.

        Returns
        -------
        SandboxResult
            Struct containing exit code, captured output, output files,
            timing, and whether the container was killed due to timeout.
        """
        if policy is None:
            policy = SecurityPolicy()

        if image not in _ALLOWED_IMAGES:
            raise ValueError(
                f"Image {image!r} is not in the allowed image list. "
                f"Allowed: {sorted(_ALLOWED_IMAGES)}"
            )

        container = None
        code_dir: tempfile.TemporaryDirectory[str] | None = None
        data_dir: tempfile.TemporaryDirectory[str] | None = None

        try:
            # ---- 1. Write code files to a temp directory for bind mount ----
            code_dir = tempfile.TemporaryDirectory(prefix="phiacta_code_")
            for relative_path, source in code_files.items():
                # Reject path traversal in file names.
                if relative_path.startswith("/") or ".." in relative_path.split("/"):
                    raise ValueError(f"Path traversal in code_files key: {relative_path!r}")
                dest = Path(code_dir.name) / relative_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(source, encoding="utf-8")

            # ---- 2. Optionally write data files to a temp directory --------
            binds: dict[str, dict[str, str]] = {
                code_dir.name: {"bind": "/code", "mode": "ro"},
            }
            if data_files:
                data_dir = tempfile.TemporaryDirectory(prefix="phiacta_data_")
                for relative_path, raw in data_files.items():
                    if relative_path.startswith("/") or ".." in relative_path.split("/"):
                        raise ValueError(f"Path traversal in data_files key: {relative_path!r}")
                    dest = Path(data_dir.name) / relative_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(raw)
                binds[data_dir.name] = {"bind": "/data", "mode": "ro"}

            # ---- 3. Build the full container configuration -----------------
            host_config = policy.to_container_config()
            host_config["binds"] = binds

            # ---- 4. Filter environment variables ----------------------------
            safe_env: dict[str, str] = {}
            if env_vars:
                for key, value in env_vars.items():
                    upper_key = key.upper()
                    if upper_key in _BLOCKED_ENV_VARS:
                        logger.warning(
                            "Blocked dangerous env var: %s", key
                        )
                        continue
                    safe_env[key] = value

            # ---- 5. Create container (not yet started) ---------------------
            container = await asyncio.to_thread(
                self._client.containers.create,
                image=image,
                command=command,
                working_dir="/code",
                detach=True,
                stdin_open=False,
                tty=False,
                environment=safe_env,
                # Flatten host_config into keyword arguments accepted by
                # the high-level Docker SDK ``create`` method.
                **host_config,
            )

            logger.info(
                "Container created: id=%s image=%s",
                container.short_id,
                image,
            )

            # ---- 5. Start container and wait with timeout ------------------
            start_time = time.monotonic()
            await asyncio.to_thread(container.start)

            timed_out = False
            try:
                exit_info = await asyncio.to_thread(
                    container.wait,
                    timeout=policy.timeout_seconds,
                )
                exit_code: int = int(exit_info.get("StatusCode", -1))
            except (
                docker.errors.APIError,
                ConnectionError,
                requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError,
            ) as exc:
                # Timeout or communication error – forcefully kill container.
                logger.warning(
                    "Container %s timed out or errored during wait: %s",
                    container.short_id,
                    exc,
                )
                timed_out = True
                exit_code = -1
                try:
                    await asyncio.to_thread(container.kill)
                except docker.errors.APIError:
                    # Container may have already exited; ignore.
                    pass

            elapsed = time.monotonic() - start_time

            # ---- 6. Capture stdout / stderr (truncated to 64 KB) -----------
            raw_stdout: bytes = await asyncio.to_thread(
                container.logs, stdout=True, stderr=False
            )
            raw_stderr: bytes = await asyncio.to_thread(
                container.logs, stdout=False, stderr=True
            )

            raw_stdout = _truncate_bytes(raw_stdout)
            raw_stderr = _truncate_bytes(raw_stderr)

            # ---- 7. Sanitize text output -----------------------------------
            stdout_text = _sanitize_output(raw_stdout.decode("utf-8", errors="replace"))
            stderr_text = _sanitize_output(raw_stderr.decode("utf-8", errors="replace"))

            # ---- 8. Copy output files from /output/ in the container -------
            output_files: dict[str, bytes] = {}
            try:
                archive_stream, _stat = await asyncio.to_thread(
                    container.get_archive, "/output/"
                )
                # get_archive returns an iterator of chunks; collect them
                # but abort if the archive exceeds our size limit.
                chunks: list[bytes] = []
                total_size = 0
                for chunk in archive_stream:
                    total_size += len(chunk)
                    if total_size > _MAX_OUTPUT_FILES_BYTES:
                        logger.warning(
                            "Output archive from container %s exceeds %d bytes limit, truncating",
                            container.short_id,
                            _MAX_OUTPUT_FILES_BYTES,
                        )
                        break
                    chunks.append(chunk)
                archive_bytes = b"".join(chunks)
                output_files = _extract_tar(archive_bytes)

                # Strip the leading "output/" prefix from extracted paths so
                # callers see clean relative names.
                cleaned: dict[str, bytes] = {}
                for name, content in output_files.items():
                    clean_name = name
                    if clean_name.startswith("output/"):
                        clean_name = clean_name[len("output/"):]
                    if clean_name:  # skip empty names (the directory entry itself)
                        cleaned[clean_name] = content
                output_files = cleaned
            except docker.errors.NotFound:
                # /output/ does not exist – perfectly fine; no output files.
                pass
            except docker.errors.APIError as exc:
                logger.warning(
                    "Failed to retrieve /output/ from container %s: %s",
                    container.short_id,
                    exc,
                )

            return SandboxResult(
                exit_code=exit_code,
                stdout=stdout_text,
                stderr=stderr_text,
                output_files=output_files,
                execution_time_seconds=round(elapsed, 3),
                timed_out=timed_out,
            )

        except docker.errors.ImageNotFound:
            logger.error("Docker image not found: %s", image)
            raise
        except docker.errors.APIError:
            logger.exception("Docker API error while running container")
            raise
        finally:
            # ---- 9. ALWAYS remove container --------------------------------
            if container is not None:
                try:
                    await asyncio.to_thread(container.remove, force=True)
                    logger.info("Container removed: id=%s", container.short_id)
                except docker.errors.APIError as exc:
                    # Log but do not raise – the caller should still get the
                    # original exception (if any).
                    logger.error(
                        "Failed to remove container %s: %s",
                        container.short_id,
                        exc,
                    )

            # Clean up temporary directories.
            if code_dir is not None:
                code_dir.cleanup()
            if data_dir is not None:
                data_dir.cleanup()
