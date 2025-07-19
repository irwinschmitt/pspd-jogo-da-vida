import socket
import configparser
import json

config = configparser.ConfigParser()
config.read("config.ini")

GATEWAY_HOST = config["network"]["server_host"]
GATEWAY_PORT = int(config["network"]["server_port"])

def enviar_requisicao_udp(pow_min, pow_max):
    payload = {
        "pow_min": pow_min,
        "pow_max": pow_max
    }

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(5.0)
        request_data = json.dumps(payload).encode("utf-8")
        sock.sendto(request_data, ((GATEWAY_HOST, GATEWAY_PORT)))
        print(f"[CLIENTE UDP] Requisição enviada: {payload}")

        try:
            response_data, _ = sock.recvfrom(4096)
            response = json.loads(response_data.decode("utf-8"))
            print(f"[CLIENTE UDP] Resposta recebida:")
            print(json.dumps(response, indent=2))
        except socket.timeout:
            print("[CLIENTE UDP] Tempo limite excedido para resposta.")

if __name__ == "__main__":
    enviar_requisicao_udp(3, 5)
