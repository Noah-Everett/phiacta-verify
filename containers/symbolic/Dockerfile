FROM python:3.12-slim

RUN useradd --create-home --shell /bin/bash runner
RUN pip install --no-cache-dir sympy

WORKDIR /work
USER runner

ENTRYPOINT ["python"]
