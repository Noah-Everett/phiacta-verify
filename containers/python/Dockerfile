# =============================================================================
# phiacta-verify: Python Runner Container
# =============================================================================
#
# Purpose:
#   Sandboxed execution environment for Python-based verification scripts.
#   Supports scientific computing, data analysis, plotting, and Jupyter
#   notebook conversion.
#
# Included packages:
#   matplotlib 3.9.3, numpy 2.2.1, scipy 1.14.1, pandas 2.2.3,
#   seaborn 0.13.2, statsmodels 0.14.4, scikit-learn 1.6.0,
#   Pillow 11.1.0, sympy 1.13.3, nbconvert 7.16.4,
#   jupyter_core 5.7.2, ipykernel 6.29.5
#
# Security measures:
#   - Multi-stage build: pip and build tools exist only in builder stage
#   - pip, setuptools, easy_install removed from final image
#   - curl, wget, and other networking tools purged from final image
#   - Non-root user "runner" (no sudo, no privilege escalation)
#   - Read-only rootfs compatible (writable: /code, /output, /tmp)
#   - Minimal attack surface via python:3.12-slim base
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder -- install Python packages with pip
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir \
    matplotlib==3.9.3 \
    numpy==2.2.1 \
    scipy==1.14.1 \
    pandas==2.2.3 \
    seaborn==0.13.2 \
    statsmodels==0.14.4 \
    scikit-learn==1.6.0 \
    Pillow==11.1.0 \
    sympy==1.13.3 \
    nbconvert==7.16.4 \
    jupyter_core==5.7.2 \
    ipykernel==6.29.5

# ---------------------------------------------------------------------------
# Stage 2: Runtime -- clean, minimal image with no package managers
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Copy installed site-packages and any console-script entry points
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

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
