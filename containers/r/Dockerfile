# =============================================================================
# phiacta-verify: R Runner Container
# =============================================================================
#
# Purpose:
#   Sandboxed execution environment for R-based verification scripts.
#   Supports tidyverse data wrangling, plotting, R Markdown rendering,
#   and structured data I/O.
#
# Included packages:
#   tidyverse, ggplot2, rmarkdown, knitr, data.table, jsonlite
#   (installed from CRAN at build time)
#
# Security measures:
#   - Multi-stage build: R package compilation happens only in builder stage
#   - curl, wget, and other networking tools purged from final image
#   - install.packages() will fail at runtime (no CRAN access, no network)
#   - Non-root user "runner" (no sudo, no privilege escalation)
#   - Read-only rootfs compatible (writable: /code, /output, /tmp)
#   - Minimal attack surface via r-base:4.4.0
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder -- install R packages from CRAN
# ---------------------------------------------------------------------------
FROM r-base:4.4.0 AS builder

RUN R -e "install.packages(c( \
      'tidyverse', \
      'ggplot2', \
      'rmarkdown', \
      'knitr', \
      'data.table', \
      'jsonlite' \
    ), repos='https://cran.r-project.org', Ncpus=parallel::detectCores())"

# ---------------------------------------------------------------------------
# Stage 2: Runtime -- clean image with pre-installed libraries only
# ---------------------------------------------------------------------------
FROM r-base:4.4.0

# Copy pre-compiled R packages from builder
COPY --from=builder /usr/local/lib/R/site-library /usr/local/lib/R/site-library

# Remove networking tools and clean up
RUN apt-get update && \
    apt-get purge -y --auto-remove curl wget netcat-openbsd 2>/dev/null; \
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

# Create non-root user
RUN useradd --create-home --no-log-init --shell /bin/false runner

# Create output directory owned by runner
RUN mkdir -p /output && chown runner:runner /output

USER runner
WORKDIR /code

ENTRYPOINT ["Rscript"]
