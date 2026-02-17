# =============================================================================
# phiacta-verify: Lean 4 Runner Container
# =============================================================================
#
# Purpose:
#   Sandboxed execution environment for Lean 4 formal-verification scripts.
#   Lean 4 is installed via elan (the Lean version manager) and pinned to
#   a specific toolchain version for reproducibility.
#
# Toolchain:
#   leanprover/lean4:v4.14.0 (installed via elan)
#
# Security measures:
#   - Multi-stage build: curl, git, and elan bootstrap stay in builder stage
#   - curl, wget, git, and other networking tools purged from final image
#   - elan update / lean package fetching will fail at runtime (no network)
#   - Non-root user "runner" (no sudo, no privilege escalation)
#   - Read-only rootfs compatible (writable: /code, /output, /tmp)
#   - Only libgmp10 runtime dependency installed in final image
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder -- install elan + Lean 4 toolchain
# ---------------------------------------------------------------------------
FROM ubuntu:24.04 AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install elan and pin the Lean 4 toolchain
RUN curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
    | bash -s -- -y --default-toolchain leanprover/lean4:v4.14.0

ENV PATH="/root/.elan/bin:${PATH}"

# Verify installation
RUN lean --version

# ---------------------------------------------------------------------------
# Stage 2: Runtime -- minimal image with Lean binary only
# ---------------------------------------------------------------------------
FROM ubuntu:24.04

# Install only the required runtime library (GMP for Lean's bignum support)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgmp10 && \
    apt-get purge -y --auto-remove curl wget netcat-openbsd 2>/dev/null; \
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

# Copy the elan/lean toolchain from builder
COPY --from=builder /root/.elan /home/runner/.elan

# Create non-root user and fix toolchain ownership
RUN useradd --create-home --no-log-init --shell /bin/false runner && \
    chown -R runner:runner /home/runner/.elan

# Create output directory owned by runner
RUN mkdir -p /output && chown runner:runner /output

USER runner
ENV PATH="/home/runner/.elan/bin:${PATH}"
WORKDIR /code

ENTRYPOINT ["lean"]
