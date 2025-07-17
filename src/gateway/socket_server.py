import socket
import json
import threading
from queue import Queue
import configparser

config = configparser.ConfigParser()
config.read("config.ini")


class GameOfLifeServer:
    def __init__(self):
        self.host = config["network"]["server_host"]
        self.port = int(config["network"]["server_port"])
        self.task_queue = Queue()
        self.results = {}
        self.engine_ports = {
            "MPI": int(config["network"]["mpi_engine_port"]),
            "SPARK": int(config["network"]["spark_engine_port"]),
        }

    def handle_client(self, conn, addr):
        print(f"Conexão estabelecida com {addr}")
        try:
            data = conn.recv(1024).decode()
            print(f"Dados recebidos do cliente: {data}")
            request = json.loads(data)
            print(f"Requisição recebida: {request}")

            pow_min = request["pow_min"]
            pow_max = request["pow_max"]
            engines = ["MPI", "SPARK"]
            results = []

            for i, pow in enumerate(range(pow_min, pow_max + 1)):
                engine = engines[i % 2]
                task = {"pow": pow}
                print(f"Distribuindo tarefa para engine: {engine} com pow: {pow}")
                result = self.dispatch_task(engine, task)
                if result is not None:
                    results.append(result)
                else:
                    results.append(
                        {"engine": engine, "pow": pow, "error": f"Sem resposta do engine {engine} para pow {pow}"}
                    )

            response = {"status": "processed", "results": results}
            print(f"Resposta enviada ao cliente: {response}")
            conn.sendall(json.dumps(response).encode())
        except Exception as e:
            print(f"Erro ao lidar com cliente {addr}: {e}")
        finally:
            print(f"Conexão encerrada com {addr}")
            conn.close()

    def dispatch_task(self, engine, task):
        print(f"Enviando tarefa para {engine}: {task}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect(("localhost", self.engine_ports[engine]))
                print(f"Conectado ao engine {engine} na porta {self.engine_ports[engine]}")
                s.sendall(json.dumps(task).encode())
                print(f"Tarefa enviada para {engine}")
                s.settimeout(5)
                data = s.recv(4096)
                if not data:
                    print(f"Nenhuma resposta recebida do engine {engine}")
                    return None
                response = json.loads(data.decode())
                print(f"Resposta recebida do engine {engine}: {response}")
                response["engine"] = engine
                response["pow"] = task["pow"]
                return response
            except ConnectionRefusedError:
                print(f"Engine {engine} offline")
                return None
            except Exception as e:
                print(f"Erro ao enviar tarefa para {engine}: {e}")
                return None

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, self.port))
            s.listen()
            print(f"Servidor ouvindo em {self.host}:{self.port}")
            threads = []
            try:
                while True:
                    conn, addr = s.accept()
                    print(f"Cliente conectado: {addr}")
                    t = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                    t.start()
                    threads.append(t)
            except KeyboardInterrupt:
                print("\nEncerrando...")
            finally:
                s.close()


if __name__ == "__main__":
    server = GameOfLifeServer()
    server.start()
