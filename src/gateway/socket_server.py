import socket
import socketserver
import json
import threading
import uuid

ENGINE_ENDPOINTS = {
    "MPI": ("mpi-engine-service", 8081),
    "SPARK": ("spark-engine-service", 8082),
}


class GatewayRequestHandler(socketserver.BaseRequestHandler):
    def _dispatch_task_to_engine(self, engine_name, task_payload):
        host, port = ENGINE_ENDPOINTS[engine_name]
        print(
            f"Thread {threading.get_ident()}: Dispatching to {engine_name} at {host}:{port}"
        )

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(300.0)
                s.connect((host, port))
                s.sendall((json.dumps(task_payload) + "\n").encode("utf-8"))
                response_data = s.recv(8192)
                if not response_data:
                    return {"error": f"No response from {engine_name} engine."}
                return json.loads(response_data.decode("utf-8"))
        except ConnectionRefusedError:
            print(
                f"ERROR: Connection refused by {engine_name} engine at {host}:{port}."
            )
            return {
                "error": f"Engine '{engine_name}' is offline or refusing connections."
            }
        except socket.timeout:
            print(f"ERROR: Timeout waiting for {engine_name} engine.")
            return {"error": f"Request to engine '{engine_name}' timed out."}
        except Exception as e:
            print(
                f"ERROR: An unexpected error occurred with {engine_name} engine: {e}"
            )
            return {
                "error": f"An unexpected error occurred while communicating with {engine_name}."
            }

    def handle(self):
        client_id = str(uuid.uuid4())
        print(
            f"Thread {threading.get_ident()}: Received connection from {self.client_address} (ClientID: {client_id})"
        )

        try:
            data = self.request.recv(1024).strip()
            request = json.loads(data.decode("utf-8"))

            pow_min = int(request["pow_min"])
            pow_max = int(request["pow_max"])

            engines = ["MPI", "SPARK"]
            results = [{} for _ in range(pow_max - pow_min + 1)]
            threads = []

            def dispatch_task(i, pow_val, engine_to_use):
                task = {"pow": pow_val, "clientId": client_id}
                result = self._dispatch_task_to_engine(engine_to_use, task)
                results[i] = result

            for i, pow_val in enumerate(range(pow_min, pow_max + 1)):
                engine_to_use = engines[i % len(engines)]
                t = threading.Thread(
                    target=dispatch_task, args=(i, pow_val, engine_to_use)
                )
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            response_payload = json.dumps(
                {
                    "status": "processed",
                    "clientId": client_id,
                    "results": results,
                }
            )
            self.request.sendall(response_payload.encode("utf-8"))

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"ERROR: Invalid request from {self.client_address}: {e}")
            error_response = json.dumps(
                {
                    "status": "error",
                    "message": "Invalid JSON request. Expected format: {'pow_min': X, 'pow_max': Y}",
                }
            )
            self.request.sendall(error_response.encode("utf-8"))
        except Exception as e:
            print(f"ERROR: An unexpected error occurred in handle(): {e}")
            error_response = json.dumps(
                {
                    "status": "error",
                    "message": "An internal server error occurred.",
                }
            )
            self.request.sendall(error_response.encode("utf-8"))
        finally:
            print(
                f"Thread {threading.get_ident()}: Connection closed for {self.client_address}"
            )


def start_udp_server(host="0.0.0.0", port=8083):
    def udp_thread():
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.bind((host, port))
        print(f"[UDP] Servidor UDP ativo em {host}:{port}")

        while True:
            try:
                data, addr = udp_sock.recvfrom(1024)
                try:
                    handler = GatewayRequestHandler(
                        request=udp_sock, client_address=addr, server=None)
                    request = handler._parse_input(data)
                    pow_min = int(request["pow_min"])
                    pow_max = int(request["pow_max"])
                    engines = ["MPI", "SPARK"]
                    results = []

                    for i, pow_val in enumerate(range(pow_min, pow_max + 1)):
                        engine = engines[i % len(engines)]
                        task = {"pow": pow_val, "clientId": str(uuid.uuid4())}
                        result = handler._dispatch_task_to_engine(engine, task)
                        results.append(result)

                    response = json.dumps({
                        "status": "processed",
                        "via": "udp",
                        "results": results
                    }).encode("utf-8")

                except Exception as e:
                    response = json.dumps({
                        "status": "error",
                        "message": str(e)
                    }).encode("utf-8")

                udp_sock.sendto(response, addr)

            except Exception as e:
                print(f"[UDP] Erro: {e}")

    t = threading.Thread(target=udp_thread, daemon=True)
    t.start()


if __name__ == "__main__":
    HOST, PORT = "0.0.0.0", 8080
    socketserver.ThreadingTCPServer.allow_reuse_address = True

    start_udp_server()

    server = socketserver.ThreadingTCPServer(
        (HOST, PORT), GatewayRequestHandler
    )
    print(f"Gateway server started at {HOST}:{PORT}")
    server.serve_forever()
