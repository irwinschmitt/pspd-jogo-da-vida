import socket
import json
import threading
import configparser
import random

config = configparser.ConfigParser()
config.read("config.ini")

GATEWAY_HOST = config["network"]["server_host"]
GATEWAY_PORT = int(config["network"]["server_port"])

def cliente_tarefa(id, powmin, powmax):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((GATEWAY_HOST, GATEWAY_PORT))
            requisicao = {"powmin": powmin, "powmax": powmax}
            sock.sendall(json.dumps(requisicao).encode())

            resposta = sock.recv(8192).decode()
            print(f"[CLIENTE {id}] Resposta: {resposta}")

    except Exception as e:
        print(f"[CLIENTE {id}] ERRO: {e}")

def simular_clientes_concorrentes(n=5):
    threads = []
    for i in range(n):
        powmin = random.randint(3, 5)
        powmax = powmin + random.randint(0, 2)
        t = threading.Thread(target=cliente_tarefa, args=(i, powmin, powmax))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

if __name__ == "__main__":
    simular_clientes_concorrentes(5)
