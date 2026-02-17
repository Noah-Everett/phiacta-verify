FROM julia:1.11

RUN useradd --create-home --shell /bin/bash runner

WORKDIR /work
USER runner

ENTRYPOINT ["julia"]
