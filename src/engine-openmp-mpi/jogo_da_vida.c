#include <arpa/inet.h>
#include <jansson.h>
#include <mpi.h>
#include <omp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define ind2d(i, j, width) ((i) * ((width) + 2) + (j))
#define BUFFER_SIZE 1024

typedef struct {
  double init_time;
  double comp_time;
  double total_time;
  long peak_mem;
  double throughput;
  int is_correct;
} PerformanceMetrics;

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
  int *tabulIn_global = NULL;
  int *tabulIn_local = NULL;
  int *tabulOut_local = NULL;
  int local_rows;
  PerformanceMetrics metrics = {0};
  double t0, t1, t2;

  t0 = wall_time();

  if (rank == 0) {
    tabulIn_global = malloc((tam + 2) * (tam + 2) * sizeof(int));
    if (!tabulIn_global)
      exit(EXIT_FAILURE);
    InitTabul_Global(tabulIn_global, tam);
  }

  int rows_per_proc = tam / size;
  int remainder = tam % size;
  local_rows = rows_per_proc + (rank < remainder ? 1 : 0);

  tabulIn_local = calloc((local_rows + 2) * (tam + 2), sizeof(int));
  tabulOut_local = calloc((local_rows + 2) * (tam + 2), sizeof(int));
  if (!tabulIn_local || !tabulOut_local)
    exit(EXIT_FAILURE);

  int *sendcounts = NULL;
  int *displs = NULL;
  if (rank == 0) {
    sendcounts = malloc(size * sizeof(int));
    displs = malloc(size * sizeof(int));
    if (!sendcounts || !displs)
      exit(EXIT_FAILURE);
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
    metrics.throughput = (double)(tam * tam * 2 * (tam - 3)) / metrics.comp_time;
    free(tabulIn_global);
    free(sendcounts);
    free(displs);
  }

  free(tabulIn_local);
  free(tabulOut_local);

  return metrics;
}

int main(int argc, char *argv[]) {
  int rank, size;
  MPI_Init(&argc, &argv);
  MPI_Comm_rank(MPI_COMM_WORLD, &rank);
  MPI_Comm_size(MPI_COMM_WORLD, &size);

  if (argc < 2) {
    if (rank == 0) {
      fprintf(stderr, "Uso: mpirun -np <num_procs> %s <PORTA>\n", argv[0]);
    }
    MPI_Finalize();
    return EXIT_FAILURE;
  }

  if (rank == 0) {
    int port = atoi(argv[1]);
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0)
      exit(EXIT_FAILURE);

    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in address;
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port);

    if (bind(server_fd, (struct sockaddr *)&address, sizeof(address)) < 0)
      exit(EXIT_FAILURE);
    if (listen(server_fd, 3) < 0)
      exit(EXIT_FAILURE);

    printf("[MPI Engine] Ouvindo na porta %d\n", port);

    int addrlen = sizeof(address);
    char buffer[BUFFER_SIZE] = {0};

    while (1) {
      int new_socket = accept(server_fd, (struct sockaddr *)&address, (socklen_t *)&addrlen);
      if (new_socket < 0)
        exit(EXIT_FAILURE);

      printf("[MPI Engine] Conexão aceita.\n");

      ssize_t bytes_read = read(new_socket, buffer, BUFFER_SIZE);
      if (bytes_read <= 0) {
        close(new_socket);
        continue;
      }
      printf("[MPI Engine] Requisição recebida: %s\n", buffer);

      char *p = strstr(buffer, "\"pow\":");
      int current_pow = 0;
      if (p)
        sscanf(p + 6, "%d", &current_pow);

      if (current_pow > 0) {
        int tam = 1 << current_pow;
        MPI_Bcast(&tam, 1, MPI_INT, 0, MPI_COMM_WORLD);

        PerformanceMetrics metrics = run_game_of_life(tam, rank, size);

        json_t *metrics_obj = json_object();
        json_object_set_new(metrics_obj, "init_time", json_real(metrics.init_time));
        json_object_set_new(metrics_obj, "comp_time", json_real(metrics.comp_time));
        json_object_set_new(metrics_obj, "total_time", json_real(metrics.total_time));
        json_object_set_new(metrics_obj, "peak_mem_kb", json_integer(metrics.peak_mem));
        json_object_set_new(metrics_obj, "throughput", json_real(metrics.throughput));
        json_object_set_new(metrics_obj, "correct", json_boolean(metrics.is_correct));

        json_t *root = json_object();
        json_object_set_new(root, "engine", json_string("MPI/OpenMP"));
        json_object_set_new(root, "board_size", json_integer(tam));
        json_object_set_new(root, "metrics", metrics_obj);

        char *response = json_dumps(root, JSON_COMPACT);
        send(new_socket, response, strlen(response), 0);
        printf("[MPI Engine] Resposta enviada.\n");

        free(response);
        json_decref(root);
      } else {
        int tam = -1;
        MPI_Bcast(&tam, 1, MPI_INT, 0, MPI_COMM_WORLD);
        close(new_socket);
        break;
      }
      close(new_socket);
    }
    close(server_fd);

  } else {
    while (1) {
      int tam;
      MPI_Bcast(&tam, 1, MPI_INT, 0, MPI_COMM_WORLD);
      if (tam == -1)
        break;
      run_game_of_life(tam, rank, size);
    }
  }

  MPI_Finalize();
  return EXIT_SUCCESS;
}
