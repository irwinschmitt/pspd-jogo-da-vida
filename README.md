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
