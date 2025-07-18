FROM ubuntu:22.04 AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    mpich \
    libmpich-dev \
    libcurl4-openssl-dev \
    libjansson-dev
WORKDIR /app
COPY . .
RUN mpicc -fopenmp -o jogo_da_vida_omp_mpi ./jogo_da_vida_omp_mpi.c -lcurl -ljansson

FROM ubuntu:22.04
RUN apt-get update && apt-get install -y --no-install-recommends \
    mpich \
    libcurl4 \
    libjansson4 \
    libgomp1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/jogo_da_vida_omp_mpi .
CMD ["mpirun", "-np", "4", "./jogo_da_vida_omp_mpi"]
