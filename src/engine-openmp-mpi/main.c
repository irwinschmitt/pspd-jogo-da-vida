#include <mpi.h>
#include <omp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#define ind2d(i, j, width) ((i) * ((width) + 2) + (j))
#define BUFFER_SIZE 1024
#define MIN_POW 3
#define MAX_POW 20

typedef struct {
  double init_time;
  double comp_time;
  double total_time;
  long peak_mem;
  double throughput;
  int is_correct;
} PerformanceMetrics;

void log_message(const char *message) {
  time_t now;
  time(&now);
  char *time_str = ctime(&now);
  time_str[strlen(time_str) - 1] = '\0';
  printf("[%s] %s\n", time_str, message);
}

double wall_time(void) {
  struct timeval tv;
  gettimeofday(&tv, NULL);
  return (tv.tv_sec + tv.tv_usec / 1000000.0);
}

long get_peak_memory_usage(void) {
  struct rusage r_usage;
  getrusage(RUSAGE_SELF, &r_usage);
  return r_usage.ru_maxrss;
}

void InitTabul_Global(int *tabulIn, int tam) {
  for (int ij = 0; ij < (tam + 2) * (tam + 2); ij++) {
    tabulIn[ij] = 0;
  }
  tabulIn[ind2d(1, 2, tam)] = 1;
  tabulIn[ind2d(2, 3, tam)] = 1;
  tabulIn[ind2d(3, 1, tam)] = 1;
  tabulIn[ind2d(3, 2, tam)] = 1;
  tabulIn[ind2d(3, 3, tam)] = 1;
}

void UmaVida_paralela(int *tabulIn_local, int *tabulOut_local, int local_rows, int tam) {
#pragma omp parallel for
  for (int i = 1; i <= local_rows; i++) {
    for (int j = 1; j <= tam; j++) {
      int vizviv = tabulIn_local[ind2d(i - 1, j - 1, tam)] + tabulIn_local[ind2d(i - 1, j, tam)] + tabulIn_local[ind2d(i - 1, j + 1, tam)] + tabulIn_local[ind2d(i, j - 1, tam)] +
                   tabulIn_local[ind2d(i, j + 1, tam)] + tabulIn_local[ind2d(i + 1, j - 1, tam)] + tabulIn_local[ind2d(i + 1, j, tam)] + tabulIn_local[ind2d(i + 1, j + 1, tam)];

      if (tabulIn_local[ind2d(i, j, tam)] && vizviv < 2)
        tabulOut_local[ind2d(i, j, tam)] = 0;
      else if (tabulIn_local[ind2d(i, j, tam)] && vizviv > 3)
        tabulOut_local[ind2d(i, j, tam)] = 0;
      else if (!tabulIn_local[ind2d(i, j, tam)] && vizviv == 3)
        tabulOut_local[ind2d(i, j, tam)] = 1;
      else
        tabulOut_local[ind2d(i, j, tam)] = tabulIn_local[ind2d(i, j, tam)];
    }
  }
}

int Correto(int *tabul, int tam) {
  int cnt = 0;
  for (int ij = 0; ij < (tam + 2) * (tam + 2); ij++) {
    cnt += tabul[ij];
  }
  return (cnt == 5 && tabul[ind2d(tam - 2, tam - 1, tam)] && tabul[ind2d(tam - 1, tam, tam)] && tabul[ind2d(tam, tam - 2, tam)] && tabul[ind2d(tam, tam - 1, tam)] && tabul[ind2d(tam, tam, tam)]);
}

PerformanceMetrics run_game_of_life(int tam, int rank, int size) {
  if (tam < (1 << MIN_POW)) {
    if (rank == 0) {
      fprintf(stderr, "Erro: Tamanho do tabuleiro %d muito pequeno (mínimo %d)\n", tam, 1 << MIN_POW);
    }

    MPI_Abort(MPI_COMM_WORLD, EXIT_FAILURE);
  }

  int *tabulIn_global = NULL;
  int *tabulIn_local = NULL;
  int *tabulOut_local = NULL;
  int local_rows;
  PerformanceMetrics metrics = {0};
  double t0, t1, t2;

  t0 = wall_time();

  if (rank == 0) {
    tabulIn_global = malloc((tam + 2) * (tam + 2) * sizeof(int));
    if (!tabulIn_global) {
      perror("Falha ao alocar memória (malloc)");
      MPI_Abort(MPI_COMM_WORLD, EXIT_FAILURE);
    }
    InitTabul_Global(tabulIn_global, tam);
  }

  int rows_per_proc = tam / size;
  int remainder = tam % size;
  local_rows = rows_per_proc + (rank < remainder ? 1 : 0);

  if (local_rows < 1) {
    fprintf(stderr, "Processo %d: Não há linhas suficientes (tam=%d, size=%d)\n", rank, tam, size);
    MPI_Abort(MPI_COMM_WORLD, EXIT_FAILURE);
  }

  tabulIn_local = calloc((local_rows + 2) * (tam + 2), sizeof(int));
  tabulOut_local = calloc((local_rows + 2) * (tam + 2), sizeof(int));
  if (!tabulIn_local || !tabulOut_local) {
    perror("Falha ao alocar memória (calloc)");
    MPI_Abort(MPI_COMM_WORLD, EXIT_FAILURE);
  }

  int *sendcounts = NULL;
  int *displs = NULL;
  if (rank == 0) {
    sendcounts = malloc(size * sizeof(int));
    displs = malloc(size * sizeof(int));
    if (!sendcounts || !displs) {
      perror("Falha ao alocar memória (malloc)");
      MPI_Abort(MPI_COMM_WORLD, EXIT_FAILURE);
    }
    for (int i = 0; i < size; i++) {
      int rows = rows_per_proc + (i < remainder ? 1 : 0);
      sendcounts[i] = rows * (tam + 2);
      int start = i * rows_per_proc + (i < remainder ? i : remainder);
      displs[i] = (start + 1) * (tam + 2);
    }
  }

  MPI_Scatterv(tabulIn_global, sendcounts, displs, MPI_INT, &tabulIn_local[ind2d(1, 0, tam)], local_rows * (tam + 2), MPI_INT, 0, MPI_COMM_WORLD);

  t1 = wall_time();
  metrics.init_time = t1 - t0;

  for (int i = 0; i < 2 * (tam - 3); i++) {
    int neighbor_up = (rank == 0) ? MPI_PROC_NULL : rank - 1;
    int neighbor_down = (rank == size - 1) ? MPI_PROC_NULL : rank + 1;

    MPI_Sendrecv(&tabulIn_local[ind2d(local_rows, 1, tam)], tam, MPI_INT, neighbor_down, 0, &tabulIn_local[ind2d(0, 1, tam)], tam, MPI_INT, neighbor_up, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);

    MPI_Sendrecv(&tabulIn_local[ind2d(1, 1, tam)], tam, MPI_INT, neighbor_up, 1, &tabulIn_local[ind2d(local_rows + 1, 1, tam)], tam, MPI_INT, neighbor_down, 1, MPI_COMM_WORLD, MPI_STATUS_IGNORE);

    UmaVida_paralela(tabulIn_local, tabulOut_local, local_rows, tam);

    MPI_Sendrecv(&tabulOut_local[ind2d(local_rows, 1, tam)], tam, MPI_INT, neighbor_down, 0, &tabulOut_local[ind2d(0, 1, tam)], tam, MPI_INT, neighbor_up, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);

    MPI_Sendrecv(&tabulOut_local[ind2d(1, 1, tam)], tam, MPI_INT, neighbor_up, 1, &tabulOut_local[ind2d(local_rows + 1, 1, tam)], tam, MPI_INT, neighbor_down, 1, MPI_COMM_WORLD, MPI_STATUS_IGNORE);

    UmaVida_paralela(tabulOut_local, tabulIn_local, local_rows, tam);
  }

  t2 = wall_time();
  metrics.comp_time = t2 - t1;
  metrics.total_time = t2 - t0;
  metrics.peak_mem = get_peak_memory_usage();

  MPI_Gatherv(&tabulIn_local[ind2d(1, 0, tam)], local_rows * (tam + 2), MPI_INT, tabulIn_global, sendcounts, displs, MPI_INT, 0, MPI_COMM_WORLD);

  if (rank == 0) {
    metrics.is_correct = Correto(tabulIn_global, tam);
    metrics.throughput = (metrics.comp_time > 1e-9) ? (double)(tam * tam * 2 * (tam - 3)) / metrics.comp_time : 0.0;
    free(tabulIn_global);
    free(sendcounts);
    free(displs);
  }

  free(tabulIn_local);
  free(tabulOut_local);

  return metrics;
}

int main(int argc, char **argv) {
  int rank, size;
  MPI_Init(&argc, &argv);
  MPI_Comm_rank(MPI_COMM_WORLD, &rank);
  MPI_Comm_size(MPI_COMM_WORLD, &size);

  if (argc != 2) {
    if (rank == 0) {
      fprintf(stderr, "Uso: %s <potência>\n", argv[0]);
    }
    MPI_Finalize();
    return EXIT_FAILURE;
  }

  int pow = atoi(argv[1]);

  if (pow < MIN_POW || pow > MAX_POW) {
    if (rank == 0) {
      fprintf(stderr, "Erro: potência deve estar entre %d e %d\n", MIN_POW, MAX_POW);
    }

    MPI_Finalize();

    return EXIT_FAILURE;
  }

  int tam = 1 << pow;
  MPI_Bcast(&tam, 1, MPI_INT, 0, MPI_COMM_WORLD);
  PerformanceMetrics metrics = run_game_of_life(tam, rank, size);

  if (rank == 0) {
    char json_output[BUFFER_SIZE];

    snprintf(json_output, BUFFER_SIZE,
             "{\"engine\":\"MPI/OpenMP\",\"board_size\":%d,\"metrics\":{"
             "\"init_time\":%.6f,\"comp_time\":%.6f,\"total_time\":%.6f,"
             "\"peak_mem_kb\":%ld,\"throughput\":%.2f,\"correct\":%s}}",
             tam, metrics.init_time, metrics.comp_time, metrics.total_time, metrics.peak_mem, metrics.throughput, metrics.is_correct ? "true" : "false");

    printf("%s\n", json_output);
  }

  MPI_Finalize();

  return EXIT_SUCCESS;
}
