FROM ubuntu:24.04

RUN apt-get update && apt-get install -y curl git && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --shell /bin/bash runner
USER runner
RUN curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | bash -s -- -y --default-toolchain leanprover/lean4:stable
ENV PATH="/home/runner/.elan/bin:${PATH}"

WORKDIR /work

ENTRYPOINT ["lean"]
