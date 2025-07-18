import socket
import json
import threading
import time
import argparse

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 30080


def run_client_request(client_id, host, port, pow_min, pow_max):
    print(f"[Cliente {client_id}] Iniciando...")

    request_payload = {
        "pow_min": pow_min,
        "pow_max": pow_max
    }
    request_data = json.dumps(request_payload).encode('utf-8')

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            print(
                f"[Cliente {client_id}] Conectado ao servidor {host}:{port}. Enviando requisição...")

            s.sendall(request_data)

            response_data = s.recv(16384)
            if response_data:
                response_json = json.loads(response_data.decode('utf-8'))
                print(f"[Cliente {client_id}] Resposta recebida:")
                print(json.dumps(response_json, indent=2))
            else:
                print(
                    f"[Cliente {client_id}] Nenhuma resposta recebida do servidor.")

    except ConnectionRefusedError:
        print(
            f"[Cliente {client_id}] ERRO: A conexão foi recusada. O serviço Gateway está no ar e acessível em {host}:{port}?")
    except socket.timeout:
        print(
            f"[Cliente {client_id}] ERRO: Timeout na conexão. O servidor demorou muito para responder.")
    except Exception as e:
        print(f"[Cliente {client_id}] ERRO: Ocorreu um erro inesperado: {e}")
    finally:
        print(f"[Cliente {client_id}] Conexão encerrada.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cliente de teste de estresse para o serviço Game of Life.")
    parser.add_argument('--host', type=str, default=DEFAULT_HOST,
                        help=f"Host do servidor Gateway (padrão: {DEFAULT_HOST})")
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help=f"Porta do servidor Gateway (padrão: {DEFAULT_PORT})")
    parser.add_argument('--clients', type=int, default=5,
                        help="Número de clientes simultâneos para simular (padrão: 5)")
    parser.add_argument('--pow-min', type=int, required=True,
                        help="Valor mínimo de POW para a requisição (ex: 8)")
    parser.add_argument('--pow-max', type=int, required=True,
                        help="Valor máximo de POW para a requisição (ex: 10)")

    args = parser.parse_args()

    print(f"--- Iniciando Teste de Estresse ---")
    print(f"Alvo: {args.host}:{args.port}")
    print(f"Simulando {args.clients} clientes simultâneos...")
    print(f"Intervalo de POW por cliente: de {args.pow_min} a {args.pow_max}")
    print("-------------------------------------\n")

    threads = []
    start_time = time.time()

    for i in range(args.clients):
        thread = threading.Thread(target=run_client_request, args=(
            i + 1, args.host, args.port, args.pow_min, args.pow_max))
        threads.append(thread)
        thread.start()
        time.sleep(0.1)

    for thread in threads:
        thread.join()

    end_time = time.time()
    print("\n--- Teste de Estresse Concluído ---")
    print(f"Tempo total de execução: {end_time - start_time:.2f} segundos.")
