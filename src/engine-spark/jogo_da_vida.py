import sys
import time
import resource
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


def executar(sc, tam):
    metrics = {
        "init_time": 0.0,
        "comp_time": 0.0,
        "total_time": 0.0,
        "peak_mem": 0,
        "throughput": 0.0,
    }

    start_time = time.time()

    init_start = time.time()
    celulas_vivas = sc.parallelize([(1, 2), (2, 3), (3, 1), (3, 2), (3, 3)]).cache()
    init_end = time.time()
    metrics["init_time"] = init_end - init_start

    num_geracoes = 4 * (tam - 3)
    comp_start = time.time()

    for i in range(num_geracoes):
        novas_celulas_vivas = evoluir_uma_geracao(celulas_vivas)
        novas_celulas_vivas.cache()

        if i % 10 == 0:
            qtd_celulas = novas_celulas_vivas.count()
            if qtd_celulas == 0:
                break

        celulas_vivas.unpersist()
        celulas_vivas = novas_celulas_vivas

    comp_end = time.time()
    metrics["comp_time"] = comp_end - comp_start

    estado_final = celulas_vivas.collect()
    end_time = time.time()

    metrics["total_time"] = end_time - start_time
    metrics["peak_mem"] = get_memory_usage()
    metrics["throughput"] = (tam * tam * num_geracoes) / metrics["comp_time"] if metrics["comp_time"] > 0 else 0.0

    return estado_final, metrics


def verificar(estado_final, tam):
    celulas_esperadas = {
        (tam - 2, tam - 1),
        (tam - 1, tam),
        (tam, tam - 2),
        (tam, tam - 1),
        (tam, tam),
    }

    return len(estado_final) == 5 and set(estado_final) == celulas_esperadas


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: spark-submit <script_name>.py <POWMIN> <POWMAX>", file=sys.stderr)
        sys.exit(-1)

    conf = SparkConf().setAppName("JogoDaVida").set("spark.driver.memory", "2g")
    sc = SparkContext(conf=conf)
    sc.setLogLevel("WARN")

    pow_min = int(sys.argv[1])
    pow_max = int(sys.argv[2])

    for p in range(pow_min, pow_max + 1):
        tam = 1 << p
        print(f"\nSimulando tabuleiro {tam}x{tam}...")

        estado_final, metrics = executar(sc, tam)
        correto = verificar(estado_final, tam)

        print("\n=== Métricas de desempenho Spark ===")
        print(f"Tamanho do tabuleiro: {tam}x{tam}")
        print(f"Tempo de inicialização: {metrics['init_time']:.6f} seg")
        print(f"Tempo de computação: {metrics['comp_time']:.6f} seg")
        print(f"Tempo total de execução: {metrics['total_time']:.6f} seg")
        print(f"Pico de uso de memória: {metrics['peak_mem']} KB")
        print(f"Vazão: {metrics['throughput']:.2f} células/seg")
        print(f"Resultado: {'CORRETO' if correto else 'INCORRETO'}")
        print("================================\n")

    sc.stop()
