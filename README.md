# phiacta-verify

Sandboxed verification engine for scientific claims. Executes notebooks, scripts, and formal proofs in isolated containers to produce reproducible, content-addressed verification results for the phiacta knowledge graph.

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the service
uvicorn phiacta_verify.main:app --reload

# Run tests
pytest

# Lint
ruff check src/ tests/
```

## Architecture

- **Runners** execute code in sandboxed Docker containers (Python, R, Julia, Lean 4, SymPy/Sage)
- **Comparators** validate outputs against expected results (exact, numerical, statistical, image)
- **Signing** produces Ed25519 signatures over content-addressed verification results
- **Queue** manages job scheduling via Redis Streams

## Docker Compose

```bash
docker compose up
```

Starts the verify API service, Redis, and runner containers.

## License

GPL-3.0-or-later
