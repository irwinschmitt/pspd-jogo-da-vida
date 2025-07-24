FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    openmpi-bin \
    libopenmpi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY main.c /app/
WORKDIR /app

RUN mpicc -o main main.c -fopenmp -O3

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openmpi-bin \
    libgomp1 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/main /usr/local/bin/main

ENTRYPOINT ["mpirun", "--allow-run-as-root"]
