import socket
import threading
import json
import configparser

config = configparser.ConfigParser()
config.read("config.ini")

GATEWAY_HOST = config["network"]["server_host"]
GATEWAY_PORT = int(config["network"]["server_port"])
MPI_PORT = int(config["network"]["mpi_engine_port"])
SPARK_PORT = int(config["network"]["spark_engine_port"])

ENGINE_LIST = ["openmp", "spark"]

def enviar_para_engine(engine, pow_value):
    engine_config = {
        "spark": (GATEWAY_HOST, SPARK_PORT),
        "openmp": (GATEWAY_HOST, MPI_PORT)
    }

    host, port = engine_config[engine]
    mensagem_json = json.dumps({"pow": pow_value})

    try:
        with socket.create_connection((host, port), timeout=5) as sock:
            sock.sendall(mensagem_json.encode())
            resposta = sock.recv(8192).decode()
            return {
                "engine": engine.upper(),
                "pow": pow_value,
                "status": "sucesso",
                "resultado": json.loads(resposta)
            }
    except Exception as e:
        return {
            "engine": engine.upper(),
            "pow": pow_value,
            "status": "erro",
            "mensagem": str(e)
        }

def tratar_cliente(conn, addr):
    print(f"[CONECTADO] {addr}")
    try:
        data = conn.recv(1024).decode()
        requisicao = json.loads(data)
        powmin = int(requisicao["powmin"])
        powmax = int(requisicao["powmax"])
        resultados = []

        for i, pow in enumerate(range(powmin, powmax + 1)):
            engine = ENGINE_LIST[i % len(ENGINE_LIST)]
            print(f"[ROTEANDO] pow={pow} -> {engine.upper()}")
            resultado = enviar_para_engine(engine, pow)
            resultados.append(resultado)

        resposta = {
            "cliente": str(addr),
            "intervalo": [powmin, powmax],
            "total_tarefas": len(resultados),
            "resultados": resultados
        }
        conn.send(json.dumps(resposta).encode())

    except Exception as e:
        erro = {"status": "erro", "mensagem": str(e)}
        conn.send(json.dumps(erro).encode())
    finally:
        conn.close()

def iniciar_gateway():
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind((GATEWAY_HOST, GATEWAY_PORT))
    servidor.listen(10)
    print(f"[GATEWAY] Escutando em {GATEWAY_HOST}:{GATEWAY_PORT}")

    while True:
        conn, addr = servidor.accept()
        thread = threading.Thread(target=tratar_cliente, args=(conn, addr))
        thread.start()

if __name__ == "__main__":
    iniciar_gateway()
