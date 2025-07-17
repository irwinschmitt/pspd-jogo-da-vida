import time
import resource
import json
import socket
from pyspark import SparkConf, SparkContext


def get_memory_usage():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def evoluir_uma_geracao(celulas_vivas_rdd):
    def gerar_atualizacoes_celula_e_vizinhos(celula):
        linha, coluna = celula
        yield (celula, (1, 0))
        for i in range(linha - 1, linha + 2):
            for j in range(coluna - 1, coluna + 2):
                if (i, j) != celula:
                    yield ((i, j), (0, 1))

    atualizacoes = celulas_vivas_rdd.flatMap(gerar_atualizacoes_celula_e_vizinhos)
    estados_celulas = atualizacoes.reduceByKey(lambda v1, v2: (v1[0] or v2[0], v1[1] + v2[1]))

    def aplicar_regras_jogo(celula_com_estado):
        celula, (esta_viva, qtd_vizinhos) = celula_com_estado
        if esta_viva and 2 <= qtd_vizinhos <= 3:
            return celula
        if not esta_viva and qtd_vizinhos == 3:
            return celula
        return None

    return estados_celulas.map(aplicar_regras_jogo).filter(lambda x: x is not None)


def processar_tarefa(sc, pow_value):
    tam = 1 << pow_value
    num_geracoes = 2 * (tam - 3)

    start_time = time.time()

    celulas_vivas = sc.parallelize([(1, 2), (2, 3), (3, 1), (3, 2), (3, 3)]).cache()
    init_time = time.time() - start_time

    comp_start = time.time()
    for _ in range(num_geracoes):
        celulas_vivas = evoluir_uma_geracao(celulas_vivas).cache()

    estado_final = celulas_vivas.collect()
    comp_time = time.time() - comp_start

    total_time = time.time() - start_time

    celulas_esperadas = {(tam - 2, tam - 1), (tam - 1, tam), (tam, tam - 2), (tam, tam - 1), (tam, tam)}
    correto = len(estado_final) == 5 and set(estado_final) == celulas_esperadas

    return {
        "engine": "SPARK",
        "board_size": tam,
        "metrics": {
            "init_time": init_time,
            "comp_time": comp_time,
            "total_time": total_time,
            "peak_mem_kb": get_memory_usage(),
            "throughput": (tam * tam * num_geracoes) / comp_time if comp_time > 0 else 0,
            "correct": correto,
        },
    }


def spark_engine(host, port):
    conf = SparkConf().setAppName("JogoDaVidaEngine").set("spark.driver.memory", "2g")
    sc = SparkContext(conf=conf)
    sc.setLogLevel("ERROR")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen()
        print(f"[Spark Engine] Ouvindo em {host}:{port}")

        while True:
            conn, addr = s.accept()
            with conn:
                print(f"[SPARK] Conexão de {addr}")
                data = conn.recv(1024).decode()
                try:
                    request = json.loads(data)
                    pow_value = request.get("pow")
                    print(f"[SPARK] Tarefa recebida: pow={pow_value}")

                    if pow_value is not None:
                        resultado = processar_tarefa(sc, pow_value)
                        conn.sendall(json.dumps(resultado).encode())
                        print("[SPARK] Resposta enviada.")
                    else:
                        conn.sendall(json.dumps({"error": "pow não especificado"}).encode())

                except Exception as e:
                    print(f"[SPARK] Erro: {e}")
                    conn.sendall(json.dumps({"error": str(e)}).encode())


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Uso: spark-submit spark_engine.py <HOST> <PORTA>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    spark_engine(host, port)
