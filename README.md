# phiacta-verify

Sandboxed verification engine for scientific claims. Executes notebooks, scripts, and formal proofs in isolated Docker containers to produce signed verification results for the phiacta knowledge graph.

## Prerequisites

- Docker daemon running (the service creates and manages containers at runtime)
- Redis server (for job queue and result storage)
- Python 3.12+

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the service (requires Docker + Redis)
uvicorn phiacta_verify.main:app --reload

# Run tests (no Docker or Redis required)
pytest

# Lint
ruff check src/ tests/
```

## Architecture

- **Runners** translate verification jobs into Docker container executions (Python, R, Julia, Lean 4, SymPy/Sage)
- **Sandbox** manages container lifecycle with strict security policies (no network, read-only rootfs, resource limits)
- **Comparators** validate outputs against expected results (exact match, numerical tolerance, statistical summary, byte similarity)
- **Signing** produces Ed25519 signatures over content-addressed verification results
- **Queue** manages job scheduling via Redis Streams with consumer groups

## Verification Levels

| Level | Meaning |
|-------|---------|
| L0 | Unverified (failed or not attempted) |
| L1 | Syntax verified (code parses without errors) |
| L2 | Execution verified (code runs to completion) |
| L3 | Output verified deterministic (outputs match expected values) |
| L4 | Output verified statistical (outputs match expected distributions) |
| L5 | Independently replicated (separate runner/environment) |
| L6 | Formally proven (e.g. Lean 4 proof type-checks) |

Note: L5 requires external orchestration (multiple independent runs). L6 is only achievable via the Lean 4 runner. Most script executions achieve L2 on success, upgrading to L3/L4 only if expected outputs are provided and match.

## Docker Compose

```bash
docker compose up
```

Starts the verify API service and Redis. Runner container images must be built separately:

```bash
docker compose --profile runners build
```

**Important**: The verify service needs access to the Docker socket (`/var/run/docker.sock`) to create runner containers. This is a Docker-in-Docker pattern -- the verify container manages sibling containers on the host Docker daemon.

## Limitations

- **Image comparator**: Uses byte-level similarity, not perceptual hashing. Useful for detecting identical files and gross corruption, but not rotation/crop/color-space changes.
- **Statistical comparator**: Uses summary statistics (mean, std, min, max, median) instead of proper KS tests. No scipy dependency.
- **No persistent storage**: Job data and results live in Redis only. No database migrations.
- **Single worker**: The background worker runs as an asyncio task inside the API process. For production, consider separate worker processes.
- **Runner images must be pre-built**: The sandbox will not pull images at runtime.

## License

GPL-3.0-or-later
