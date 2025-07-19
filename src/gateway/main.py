import socket
import socketserver
import threading
import json
import uuid
import time
from kubernetes import client, config, watch


SPARK_IMAGE = "irwinschmitt/jogo-da-vida-engine-spark:latest"
MPI_IMAGE = "irwinschmitt/jogo-da-vida-engine-mpi:latest"
HOST, PORT = "0.0.0.0", 8080

try:
    config.load_incluster_config()
except config.ConfigException:
    print("Not in a cluster, using local kubeconfig")
    config.load_kube_config()

batch_v1 = client.BatchV1Api()
core_v1 = client.CoreV1Api()


def create_job_object(engine: str, tam: int, batch_id: str) -> client.V1Job:
    job_name = f"gameoflife-{engine}-tam-{tam}-{batch_id[:8]}"
    print(f"[{threading.get_ident()}] Defining job: {job_name}")

    if engine.lower() == 'spark':
        image = SPARK_IMAGE
        command = ["/opt/bitnami/spark/bin/spark-submit"]
        args = [
            "--master", "spark://spark-master:7077",
            "--class", "org.apache.spark.deploy.SparkSubmit",
            "--conf", "spark.executor.memory=2G",
            "--conf", "spark.executor.cores=1",
            "--conf", "spark.driver.memory=1G",
            "/app/main.py",
            str(tam)
        ]
    elif engine.lower() == 'mpi':
        image = MPI_IMAGE
        command = ["mpirun", "-np", "3", "--allow-run-as-root",
                   "/app/jogo_da_vida_omp_mpi", str(tam)]
        args = []
    else:
        raise ValueError(f"Unknown engine: {engine}")

    container = client.V1Container(
        name=f"engine-{engine}",
        image=image,
        command=command,
        args=args,
        resources=client.V1ResourceRequirements(
            requests={"cpu": "500m", "memory": "512Mi"},
            limits={"cpu": "1", "memory": "2Gi"}
        )
    )

    pod_template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(
            labels={"app": "gameoflife-job", "batch-id": batch_id}),
        spec=client.V1PodSpec(restart_policy="Never", containers=[container])
    )

    job_spec = client.V1JobSpec(
        template=pod_template,
        backoff_limit=2,
        ttl_seconds_after_finished=600
    )

    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name, labels={
                                     "batch-id": batch_id}),
        spec=job_spec
    )
    return job


def dispatch_and_monitor_job(engine: str, tam: int, batch_id: str, results_list: list, index: int):
    thread_id = threading.get_ident()
    job = None
    try:
        job = create_job_object(engine, tam, batch_id)
        job_name = job.metadata.name

        batch_v1.create_namespaced_job(body=job, namespace="default")
        print(f"[{thread_id}] Submitted job '{job_name}' for tam={tam}")

        w = watch.Watch()
        for event in w.stream(batch_v1.list_namespaced_job, namespace="default", label_selector=f"batch-id={batch_id}", field_selector=f"metadata.name={job_name}", timeout_seconds=900):
            status = event['object'].status
            if status.succeeded:
                print(f"[{thread_id}] Job '{job_name}' succeeded.")
                w.stop()
                break
            if status.failed:
                print(f"[{thread_id}] Job '{job_name}' failed.")
                raise RuntimeError(f"Job {job_name} failed.")

        pod_label_selector = f"job-name={job_name}"
        if engine.lower() == 'mpi':
            results_list[index] = {
                "status": "not_implemented",
                "pow": tam,
                "engine": engine,
                "message": "MPI engine is not implemented yet."
            }
            return

        pods = core_v1.list_namespaced_pod(
            namespace="default", label_selector=pod_label_selector)
        pod_name = pods.items.metadata.name

        log_data = core_v1.read_namespaced_pod_log(
            name=pod_name, namespace="default")

        result_json = None
        for line in log_data.strip().split('\n'):
            try:
                result_json = json.loads(line)
            except json.JSONDecodeError:
                continue

        if result_json is None:
            raise ValueError("No valid JSON result found in pod logs.")

        results_list[index] = result_json

    except Exception as e:
        print(f"[{thread_id}] ERROR processing tam={tam}: {e}")
        error_result = {
            "status": "error",
            "pow": tam,
            "engine": engine,
            "message": str(e)
        }
        if job:
            error_result["job_name"] = job.metadata.name
        results_list[index] = error_result


class GatewayRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        client_address = self.client_address
        print(f"Received connection from {client_address}")

        try:
            data = self.request.recv(1024).strip().decode('utf-8')
            if not data:
                print(f"Connection from {client_address} closed with no data.")
                return

            request = json.loads(data)
            pow_min = int(request['pow_min'])
            pow_max = int(request['pow_max'])
            engine = request.get('engine', 'spark')

            print(
                f"Processing request for pow range [{pow_min}-{pow_max}] using '{engine}' engine.")

            batch_id = str(uuid.uuid4())

            threads =
            num_tasks = pow_max - pow_min + 1
            results = [{} for _ in range(num_tasks)]

            for i, pow_val in enumerate(range(pow_min, pow_max + 1)):
                thread = threading.Thread(
                    target=dispatch_and_monitor_job,
                    args=(engine, pow_val, batch_id, results, i)
                )
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            print(f"All jobs for batch {batch_id} completed.")

            final_response = {
                "batch_id": batch_id,
                "status": "processed",
                "results": results
            }
            self.request.sendall(json.dumps(
                final_response, indent=2).encode('utf-8'))

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"ERROR: Invalid request from {client_address}: {e}")
            error_response = json.dumps(
                {"status": "error", "message": "Invalid request format."})
            self.request.sendall(error_response.encode('utf-8'))
        except Exception as e:
            print(f"ERROR: An unexpected server error occurred: {e}")
            error_response = json.dumps(
                {"status": "error", "message": "Internal server error."})
            self.request.sendall(error_response.encode('utf-8'))
        finally:
            print(f"Connection closed for {client_address}")


if __name__ == "__main__":
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    server = socketserver.ThreadingTCPServer(
        (HOST, PORT), GatewayRequestHandler)

    print(f"Gateway server started at {HOST}:{PORT}")
    print("Waiting for client connections...")

    server.serve_forever()
