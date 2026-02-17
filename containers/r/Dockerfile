FROM r-base:4.4.0

RUN useradd --create-home --shell /bin/bash runner

WORKDIR /work
USER runner

ENTRYPOINT ["Rscript"]
