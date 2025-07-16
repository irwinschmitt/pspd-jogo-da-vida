#include <mpi.h>
#include <omp.h>
#include <stdio.h>
#include <stdlib.h>

#define ind2d(i, j, width) (i) * (width + 2) + (j)

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

int run_game_of_life(int tam, int rank, int size) {
  int *tabulIn_global = NULL;
  int *tabulIn_local, *tabulOut_local;
  int local_rows;
  int is_correct = 0;

  if (rank == 0) {
    tabulIn_global = (int *)malloc((tam + 2) * (tam + 2) * sizeof(int));
    InitTabul_Global(tabulIn_global, tam);
  }

  int rows_per_proc = tam / size;
  int remainder = tam % size;
  local_rows = rows_per_proc + (rank < remainder ? 1 : 0);

  tabulIn_local = (int *)calloc((local_rows + 2) * (tam + 2), sizeof(int));
  tabulOut_local = (int *)calloc((local_rows + 2) * (tam + 2), sizeof(int));

  int *sendcounts = (rank == 0) ? (int *)malloc(size * sizeof(int)) : NULL;
  int *displs = (rank == 0) ? (int *)malloc(size * sizeof(int)) : NULL;

  if (rank == 0) {
    for (int i = 0; i < size; i++) {
      int rows = rows_per_proc + (i < remainder ? 1 : 0);
      sendcounts[i] = rows * (tam + 2);
      int start = i * rows_per_proc + (i < remainder ? i : remainder);
      displs[i] = (start + 1) * (tam + 2);
    }
  }

  MPI_Scatterv(tabulIn_global, sendcounts, displs, MPI_INT, &tabulIn_local[ind2d(1, 0, tam)], local_rows * (tam + 2), MPI_INT, 0, MPI_COMM_WORLD);

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

  MPI_Gatherv(&tabulIn_local[ind2d(1, 0, tam)], local_rows * (tam + 2), MPI_INT, tabulIn_global, sendcounts, displs, MPI_INT, 0, MPI_COMM_WORLD);

  if (rank == 0) {
    is_correct = Correto(tabulIn_global, tam);
    free(tabulIn_global);
    free(sendcounts);
    free(displs);
  }

  free(tabulIn_local);
  free(tabulOut_local);

  return is_correct;
}

int main(int argc, char *argv[]) {
  int rank, size;
  MPI_Init(&argc, &argv);
  MPI_Comm_rank(MPI_COMM_WORLD, &rank);
  MPI_Comm_size(MPI_COMM_WORLD, &size);

  if (argc < 3) {
    if (rank == 0) {
      fprintf(stderr,
              "Uso: mpirun -np <num_procs> %s <POWMIN> "
              "<POWMAX>\n",
              argv[0]);
    }
    MPI_Finalize();
    return 1;
  }

  int pow_min = atoi(argv[1]);
  int pow_max = atoi(argv[2]);

  if (pow_min <= 0 || pow_max <= 0 || pow_min > pow_max) {
    if (rank == 0) {
      fprintf(stderr, "Forneça um intervalo válido para "
                      "pow (ex: 3 10).\n");
    }
    MPI_Finalize();
    return 1;
  }

  for (int p = pow_min; p <= pow_max; p++) {
    int current_tam = 1 << p;
    int result = run_game_of_life(current_tam, rank, size);

    if (rank == 0) {
      char *result_label = result ? "CORRETO" : "ERRADO";

      printf("Tabuleiro: %dx%d | Resultado: %s\n", current_tam, current_tam, result_label);
    }
    MPI_Barrier(MPI_COMM_WORLD);
  }

  MPI_Finalize();
  return 0;
}
