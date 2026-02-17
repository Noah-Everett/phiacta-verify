# =============================================================================
# phiacta-verify: Symbolic Math Runner Container
# =============================================================================
#
# Purpose:
#   Lightweight sandboxed environment for symbolic mathematics verification.
#   Contains only SymPy and NumPy -- a deliberately minimal footprint for
#   tasks that require computer algebra (symbolic differentiation, integration,
#   equation solving, simplification) but no heavy data-science stack.
#
# Included packages:
#   sympy 1.13.3, numpy 2.2.1
#
# Security measures:
#   - Multi-stage build: pip and build tools exist only in builder stage
#   - pip, setuptools, easy_install removed from final image
#   - curl, wget, and other networking tools purged from final image
#   - Non-root user "runner" (no sudo, no privilege escalation)
#   - Read-only rootfs compatible (writable: /code, /output, /tmp)
#   - Smallest possible Python image (python:3.12-slim)
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder -- install symbolic math packages with pip
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir \
    sympy==1.13.3 \
    numpy==2.2.1

# ---------------------------------------------------------------------------
# Stage 2: Runtime -- clean, minimal image with no package managers
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Copy installed site-packages only (no console scripts needed)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Remove package managers and networking tools from the final image
RUN pip uninstall -y pip setuptools wheel 2>/dev/null; \
    rm -rf /usr/local/bin/pip* /usr/local/bin/easy_install* /usr/local/bin/wheel*; \
    rm -rf /usr/local/lib/python3.12/ensurepip; \
    apt-get update && \
    apt-get purge -y --auto-remove curl wget netcat-openbsd 2>/dev/null; \
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

# Create non-root user
RUN useradd --create-home --no-log-init --shell /bin/false runner

# Create output directory owned by runner
RUN mkdir -p /output && chown runner:runner /output

USER runner
WORKDIR /code

ENTRYPOINT ["python"]
