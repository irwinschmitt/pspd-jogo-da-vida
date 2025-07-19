import logging
import time
import json
import platform
import numpy as np
from pyspark.sql import SparkSession
from pyspark import SparkContext
import socket

try:
    import resource
except ImportError:
    resource = None

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_peak_memory_kb():
    if resource:
        mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if platform.system() == "Darwin":
            return mem / 1024
        return mem
    return -1


def init_tabul(tam: int) -> np.ndarray:
    board = np.zeros((tam + 2, tam + 2), dtype=np.int32)
    board[1, 2] = 1
    board[2, 3] = 1
    board[3, 1] = 1
    board[3, 2] = 1
    board[3, 3] = 1
    return board


def _calculate_new_row(
    triplet: tuple[np.ndarray, np.ndarray, np.ndarray], tam: int
) -> np.ndarray:
    row_above, current_row, row_below = triplet
    new_row = np.copy(current_row)
    for j in range(1, tam + 1):
        vizviv = (
            row_above[j - 1]
            + row_above[j]
            + row_above[j + 1]
            + current_row[j - 1]
            + current_row[j + 1]
            + row_below[j - 1]
            + row_below[j]
            + row_below[j + 1]
        )
        cell_state = current_row[j]
        if cell_state == 1 and (vizviv < 2 or vizviv > 3):
            new_row[j] = 0
        elif cell_state == 0 and vizviv == 3:
            new_row[j] = 1
        else:
            new_row[j] = cell_state
    return new_row


def uma_vida_spark(
    board: np.ndarray, sc: SparkContext, tam: int
) -> np.ndarray:
    rdd_prev = sc.parallelize(board[0:-2])
    rdd_curr = sc.parallelize(board[1:-1])
    rdd_next = sc.parallelize(board[2:])
    triplets_rdd = (
        rdd_prev.zip(rdd_curr)
        .zip(rdd_next)
        .map(lambda x: (x[0][0], x[0][1], x[1]))
    )
    new_rows_rdd = triplets_rdd.map(
        lambda triplet: _calculate_new_row(triplet, tam)
    )
    new_rows_list = new_rows_rdd.collect()
    new_board = np.zeros((tam + 2, tam + 2), dtype=np.int32)
    new_board[1:-1, :] = np.array(new_rows_list)
    return new_board


def correto(board: np.ndarray, tam: int) -> bool:
    live_cell_count = np.sum(board)
    final_pattern_correct = (
        board[tam - 2, tam - 1] == 1
        and board[tam - 1, tam] == 1
        and board[tam, tam - 2] == 1
        and board[tam, tam - 1] == 1
        and board[tam, tam] == 1
    )
    return bool(live_cell_count == 5 and final_pattern_correct)


def main(pow_val: int, sc: SparkContext):
    tam = 1 << pow_val
    t_total_start = time.time()
    t0 = time.time()
    tabul_in = init_tabul(tam)
    t1 = time.time()
    init_time = t1 - t0
    iterations_outer_loop = 2 * (tam - 3)
    total_generations = iterations_outer_loop * 2
    logging.info(
        f"Tamanho {tam}x{tam}: Iniciando {total_generations} gerações..."
    )
    for _ in range(iterations_outer_loop):
        tabul_out = uma_vida_spark(tabul_in, sc, tam)
        tabul_in = uma_vida_spark(tabul_out, sc, tam)
    t2 = time.time()
    comp_time = t2 - t1
    is_correct = correto(tabul_in, tam)
    peak_mem_kb = get_peak_memory_kb()
    throughput = (
        (tam * tam * total_generations) / comp_time
        if comp_time > 0
        else 0.0
    )
    total_time = time.time() - t_total_start
    metrics = {
        "init_time": init_time,
        "comp_time": comp_time,
        "total_time": total_time,
        "peak_mem_kb": peak_mem_kb,
        "throughput_cells_per_sec": throughput,
        "correct": is_correct,
    }
    result_json = {
        "engine": "Python/PySpark",
        "pow_value": pow_val,
        "board_size": tam,
        "metrics": metrics,
    }
    result_str = json.dumps(result_json, indent=4)
    print(result_str)
    return result_str


def run_tcp_server():
    HOST = "0.0.0.0"
    PORT = 8082
    spark = (
        SparkSession.builder.appName(
            "PySpark Game of Life TCP Server"
        )
        .master("local[*]")
        .getOrCreate()
    )
    sc = spark.sparkContext
    logging.info(f"TCP Server listening on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        while True:
            conn, addr = s.accept()
            with conn:
                logging.info(f"Connection from {addr}")
                try:
                    data = b""
                    while True:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        data += chunk
                        if b"\n" in chunk:
                            break
                    try:
                        payload = json.loads(data.decode().strip())
                        pow_val = int(payload.get("pow"))
                    except Exception:
                        logging.error(
                            "Invalid payload received.", exc_info=True)
                        conn.sendall(b'{"error":"Invalid payload"}\n')
                        continue
                    result = main(pow_val, sc)
                    conn.sendall(result.encode() + b"\n")
                except Exception:
                    logging.error("Error during computation.", exc_info=True)
                    conn.sendall(b'{"error":"Computation error"}\n')
    spark.stop()
    logging.info("SparkSession finalizada.")


if __name__ == "__main__":
    run_tcp_server()
