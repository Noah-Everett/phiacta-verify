FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir .

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY src/ src/

RUN useradd --create-home --shell /bin/bash verify
USER verify

EXPOSE 8000
CMD ["uvicorn", "phiacta_verify.main:app", "--host", "0.0.0.0", "--port", "8000"]
