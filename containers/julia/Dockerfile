# =============================================================================
# phiacta-verify: Julia Runner Container
# =============================================================================
#
# Purpose:
#   Sandboxed execution environment for Julia-based verification scripts.
#   Supports plotting, data frames, CSV I/O, statistics, and JSON.
#   All packages are precompiled so first-use latency is eliminated.
#
# Included packages:
#   Plots, DataFrames, CSV, Statistics (stdlib), StatsBase, JSON
#
# Security measures:
#   - Multi-stage build: Pkg manager download cache stays in builder stage
#   - curl, wget, and other networking tools purged from final image
#   - Pkg.add() will fail at runtime (no network, no registry)
#   - Non-root user "runner" (no sudo, no privilege escalation)
#   - Read-only rootfs compatible (writable: /code, /output, /tmp)
#   - Julia package depot transferred with correct ownership
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder -- install and precompile Julia packages
# ---------------------------------------------------------------------------
FROM julia:1.10 AS builder

# Install packages and force precompilation by loading them
RUN julia -e ' \
    using Pkg; \
    Pkg.add(["Plots", "DataFrames", "CSV", "StatsBase", "JSON"]); \
    using Plots, DataFrames, CSV, Statistics, StatsBase, JSON; \
    println("All packages precompiled successfully.")'

# ---------------------------------------------------------------------------
# Stage 2: Runtime -- clean image with precompiled depot
# ---------------------------------------------------------------------------
FROM julia:1.10

# Copy the entire Julia depot (packages + precompile caches)
COPY --from=builder /root/.julia /home/runner/.julia

# Remove networking tools and clean up
RUN apt-get update && \
    apt-get purge -y --auto-remove curl wget netcat-openbsd 2>/dev/null; \
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

# Create non-root user and fix depot ownership
RUN useradd --create-home --no-log-init --shell /bin/false runner && \
    chown -R runner:runner /home/runner/.julia

# Create output directory owned by runner
RUN mkdir -p /output && chown runner:runner /output

# Point Julia to the runner's depot
ENV JULIA_DEPOT_PATH="/home/runner/.julia"

USER runner
WORKDIR /code

ENTRYPOINT ["julia"]
