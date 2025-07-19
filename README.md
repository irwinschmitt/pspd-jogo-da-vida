# Jogo da Vida

## Organização do repositório

```bash
.
├── 📁 analysis/
│   ├── 📁 elasticsearch/       # Configurações de índices do Elasticsearch
│   └── 📁 kibana/              # Dashboards do Kibana (JSON exportados)
├── 📁 docs/                    # Documentação complementar do projeto
├── 📁 infra/
│   ├── 📁 kubernetes/          # Manifestos YAML para Kubernetes
│   └── 📁 docker/              # Dockerfiles base e scripts auxiliares
└── 📁 src/
    ├── 📁 engine-openmp-mpi/    # Código C, Makefile e Dockerfile (OpenMP/MPI)
    ├── 📁 engine-spark/         # Código PySpark, requirements.txt e Dockerfile
    ├── 📁 gateway/              # Socket Server/Kafka, dependências e Dockerfile
    └── 📁 test-client/          # Cliente de testes de estresse
```

## Pré-requisitos

- Docker: https://docs.docker.com/engine/install/
- Kubectl: https://kubernetes.io/docs/tasks/tools/
- K3d: https://k3d.io/stable/#learning

## Execução

1. Crie um cluster k3d:

   ```bash
   k3d cluster create jogo-da-vida-cluster --servers 1 --agents 2 --port 30080:30080@loadbalancer --port 30100:30100@loadbalancer
   ```

2. Aplique o manifesto do Kubernetes:

   ```bash
   kubectl apply -f infra/kubernetes/app/
   ```

3. Verifique se os pods estão em execução (`Running`):

   ```bash
   kubectl get pods
   ```

4. Execute o cliente de testes:

   ```bash
   python test_client.py --clients 2 --pow-min 4 --pow-max 5
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

6. Visualize os logs no Kibana: `{"engine":"MPI/OpenMP","board_size":16,"metrics":{"init_time":0.000006,"comp_time":3.164810,"total_time":3.164816,"peak_mem_kb":10988,"throughput":2103.13,"correct":true}}`

Obs.: apenas engine do openmp tá enviando agora.
