# Jogo da Vida

## Organização do repositório

```bash
.
├── 📁 analysis/
│   ├── 📁 elasticsearch/       # Configurações de índices do Elasticsearch
│   └── 📁 kibana/              # Dashboards do Kibana (JSON exportados)
├── 📁 infra/
│   ├── 📁 kubernetes/          # Manifestos YAML para Kubernetes
│   └── 📁 docker/              # Dockerfiles base e scripts auxiliares
└── 📁 src/
    ├── 📁 engine-openmp-mpi/    # Código da engine OpenMP/MPI
    ├── 📁 engine-spark/         # Código da engine com Apache Spark
    ├── 📁 gateway/              # Código do gateway
    └── 📁 test-client/          # Cliente de testes de estresse
```

## Pré-requisitos

- Docker: https://docs.docker.com/engine/install/
- Kubectl: https://kubernetes.io/docs/tasks/tools/
- K3d: https://k3d.io/stable/#learning

## Testar localmente

Apesar do sistema ser construído para um cluster multi nó com 1 master e 2 workers, é possível testá-lo em apenas uma máquina usando, por exemplo, o k3d.

1. Crie o cluster.

   ```bash
   k3d cluster create \
   jogo-da-vida-cluster \
   --servers 1 \
   --agents 2 \
   --port 30080:30080@loadbalancer \
   --port 30100:30100@loadbalancer
   ```

2. Aplique os manifestos do Kubernetes as engines.

   1. Engine Spark:

      ```bash
      kubectl apply -f infra/kubernetes/app/spark
      ```

   2. Engine MPI/OpenMP:

      ```bash
      kubectl apply -f infra/kubernetes/app/mpi-omp
      ```

3. Aplique os manifestos de monitoramento.

   1. Manifesto dos CRDs do ECK (Elastic Cloud on Kubernetes).

      ```bash
      kubectl create -f https://download.elastic.co/downloads/eck/3.0.0/crds.yaml
      ```

   2. Manifesto do operador ECK.

      ```bash
      kubectl apply -f https://download.elastic.co/downloads/eck/3.0.0/operator.yaml
      ```

   3. Manifesto locais.

      ```bash
      kubectl apply -f infra/kubernetes/logging
      ```

4. Verifique se os pods rodando corretamente.

   ```bash
   kubectl get pods
   ```

5. Execute o cliente de testes.

   ```bash
   python test_client.py \
   --clients 2 \
   --pow-min 4 \
   --pow-max 10
   ```

## Fluxo completo

1. Cria os scripts;
2. Cria o Dockerfile;
3. Cria a imagem Docker, ex.: `docker build -t jogo-da-vida-engine-mpi .`;
4. Adiciona uma tag à imagem, ex.: `docker tag jogo-da-vida-engine-mpi irwinschmitt/jogo-da-vida-engine-mpi:latest`;
5. Publica a imagem no Docker Hub, ex.: `docker push irwinschmitt/jogo-da-vida-engine-mpi:latest `;
6. Cria o manifesto do Kubernetes (`.yaml`);
7. Adiciona a imagem ao manifesto, ex.: `image: irwinschmitt/jogo-da-vida-engine-mpi:latest`;
8. Cria o cluster K3d, ex.: `k3d cluster create jogo-da-vida-cluster --servers 1 --agents 2 --port 30080:30080@loadbalancer --port 30100:30100@loadbalancer`;
9. Aplica o manifesto do Kubernetes, ex.: `kubectl apply -f infra/kubernetes/`;
10. Aguarda até que estejam com o status `Running` (`kubectl get pods`);
11. Executa o cliente de testes: `python test_client.py --clients 1 --pow-min 4 --pow-max 5`.

# ElasticSearch e Kibana

1.  **Instale os Custom Resource Definitions (CRDs) do ECK**:

    ```bash
    kubectl create -f https://download.elastic.co/downloads/eck/3.0.0/crds.yaml
    ```

    Isso estende a API do Kubernetes para entender os recursos da Elastic.

2.  **Instale o Operator do ECK**:

    ```bash
    kubectl apply -f https://download.elastic.co/downloads/eck/3.0.0/operator.yaml
    ```

    Isso implanta o controlador do ECK no namespace `elastic-system`.

3.  **Verifique a instalação do Operator**:

    ```bash
    kubectl -n elastic-system get pods
    ```

    Aguarde até que `elastic-operator-0` esteja `Running`.

4.  Aplique os manifestos:

    ```bash
    kubectl apply -f elasticsearch.yaml

    kubectl apply -f kibana.yaml

    kubectl apply -f filebeat-rbac.yaml

    kubectl apply -f filebeat.yaml
    ```

5.  Execute o cliente de testes:

    ```bash
    python src/test-client/test_client.py --host 127.0.0.1 --port 30080 --clients 2 --pow-min 4 --pow-max 5
    ```

6.  Visualize os logs no Kibana: `{"engine":"MPI/OpenMP","board_size":16,"metrics":{"init_time":0.000006,"comp_time":3.164810,"total_time":3.164816,"peak_mem_kb":10988,"throughput":2103.13,"correct":true}}`

Obs.: apenas engine do openmp tá enviando agora.
