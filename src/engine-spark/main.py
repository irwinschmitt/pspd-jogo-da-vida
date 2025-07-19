import sys
import time
import json

try:
    import resource
except ImportError:
    resource = None

from pyspark.sql import SparkSession


def ind2d(i, j, tam):
    return (i) * (tam + 2) + j


def get_neighbors(i, j, tam):
    return [
        ind2d(i - 1, j - 1, tam), ind2d(i - 1,
                                        j, tam), ind2d(i - 1, j + 1, tam),
        ind2d(i, j - 1, tam),                         ind2d(i, j + 1, tam),
        ind2d(i + 1, j - 1, tam), ind2d(i + 1,
                                        j, tam), ind2d(i + 1, j + 1, tam)
    ]


def compute_next_gen(partition, tam, broadcast_board):
    board_broadcast = broadcast_board.value
    output_partition = []

    for cell_index in partition:
        i = cell_index // (tam + 2)
        j = cell_index % (tam + 2)

        if i == 0 or i > tam or j == 0 or j > tam:
            continue

        vizviv = sum(board_broadcast[n_idx]
                     for n_idx in get_neighbors(i, j, tam))

        current_state = board_broadcast[cell_index]
        next_state = current_state

        if current_state == 1 and (vizviv < 2 or vizviv > 3):
            next_state = 0
        elif current_state == 0 and vizviv == 3:
            next_state = 1

        output_partition.append((cell_index, next_state))

    return iter(output_partition)


def init_tabul(tam):
    size = (tam + 2) * (tam + 2)
    tabul = [0] * size
    tabul[ind2d(1, 2, tam)] = 1
    tabul[ind2d(2, 3, tam)] = 1
    tabul[ind2d(3, 1, tam)] = 1
    tabul[ind2d(3, 2, tam)] = 1
    tabul[ind2d(3, 3, tam)] = 1
    return tabul


def correto(tabul, tam):
    cnt = sum(tabul)
    final_pos_correct = (
        tabul[ind2d(tam - 2, tam - 1, tam)] == 1 and
        tabul[ind2d(tam - 1, tam, tam)] == 1 and
        tabul[ind2d(tam, tam - 2, tam)] == 1 and
        tabul[ind2d(tam, tam - 1, tam)] == 1 and
        tabul[ind2d(tam, tam, tam)] == 1
    )
    return cnt == 5 and final_pos_correct


def get_peak_memory_usage():
    if resource:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return -1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: spark-submit main.py <tam>", file=sys.stderr)
        sys.exit(-1)

    tam = int(sys.argv[1])
    num_generations = 4 * (tam - 3)

    total_start_time = time.time()

    spark = SparkSession.builder.appName(f"GameOfLife_tam{tam}").getOrCreate()
    sc = spark.sparkContext

    init_start_time = time.time()
    initial_board = init_tabul(tam)
    cell_indices = list(range(len(initial_board)))
    rdd = sc.parallelize(cell_indices, 8)
    init_end_time = time.time()

    current_board = initial_board

    comp_start_time = time.time()
    for gen in range(num_generations):
        board_b = sc.broadcast(current_board)

        next_gen_rdd = rdd.mapPartitions(
            lambda part: compute_next_gen(part, tam, board_b))

        next_board_state_updates = next_gen_rdd.collect()
        new_board = list(current_board)
        for index, new_value in next_board_state_updates:
            new_board[index] = new_value
        current_board = new_board
        board_b.unpersist()
    comp_end_time = time.time()

    total_end_time = time.time()

    comp_time = comp_end_time - comp_start_time
    metrics = {
        'init_time': init_end_time - init_start_time,
        'comp_time': comp_time,
        'total_time': total_end_time - total_start_time,
        'peak_mem_kb': get_peak_memory_usage(),
        'throughput': (tam * tam * num_generations) / comp_time if comp_time > 0 else 0,
        'correct': correto(current_board, tam)
    }
    final_result = {
        "engine": "Spark",
        "board_size": tam,
        "metrics": metrics
    }
    print(json.dumps(final_result))

    spark.stop()
