# Docker / Infraestrutura

Arquivos de configuração Docker para o CDB Shalom.

## Estrutura

```
infra/docker/
├── README.md
├── docker-compose.yml          ← Produção
├── docker-compose.dev.yml      ← Desenvolvimento
└── ollama/
    └── Modelfile               ← Configuração do modelo Ollama
```

## Uso

```bash
# Desenvolvimento
docker compose -f infra/docker/docker-compose.dev.yml up -d

# Produção
docker compose -f infra/docker/docker-compose.yml up -d
```

## Serviços

- **backend** — FastAPI (Python)
- **frontend** — Vite + React
- **whatsapp-service** — Node.js + whatsapp-web.js
- **celery-worker** — Celery para tarefas assíncronas
- **redis** — Cache e broker Celery
- **postgres** — Banco de dados (produção)
- **ollama** — Modelo de IA local

> **Nota:** Em desenvolvimento, use SQLite em vez de PostgreSQL para simplicidade.