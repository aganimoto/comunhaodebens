# CDB Shalom

Sistema de gestão de contribuições e comunicação via WhatsApp para a Comunidade Católica Shalom.

## Visão Geral

O CDB Shalom é um sistema modular que automatiza o recebimento, processamento e gestão de comprovantes de contribuição dos membros da comunidade através do WhatsApp. Utiliza inteligência artificial local (Ollama) para extrair dados de imagens de comprovantes e sincroniza com Google Sheets.

### Principais Funcionalidades

- 📱 **Recebimento de comprovantes via WhatsApp** — membros enviam fotos/extratos e o sistema processa automaticamente
- 🤖 **OCR + IA local** — extrai dados digitais de comprovantes usando Ollama + LLaVA
- 📊 **Sincronização com Google Sheets** — mantém planilhas atualizadas em tempo real
- 📈 **Dashboard administrativo** — métricas, pendências, relatórios
- 🔄 **Relatórios mensais automáticos** — geração e distribuição via WhatsApp
- 🔐 **Autenticação JWT** — controle de acesso por perfil (admin, financeiro, consulta)

## Arquitetura

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   Backend API    │────▶│   WhatsApp      │
│   (Vite+React)  │◀────│   (FastAPI)      │◀────│   Service       │
│   :5173         │     │   :8000          │     │   :3000         │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
             ┌──────────┐ ┌──────────┐ ┌──────────┐
             │PostgreSQL│ │  Redis   │ │  Ollama  │
             │ (SQLite  │ │ (Celery  │ │ (IA      │
             │  em dev) │ │  broker) │ │  local)  │
             └──────────┘ └──────────┘ └──────────┘
```

## Estrutura de Diretórios

```
comunhaodebens/
├── README.md
├── .gitignore
│
├── config/                     ← Variáveis de ambiente
│   ├── .env.example
│   └── README.md
│
├── infra/
│   └── docker/                 ← Docker Compose e configurações
│       ├── docker-compose.yml
│       ├── docker-compose.dev.yml
│       ├── ollama/Modelfile
│       └── README.md
│
├── scripts/
│   ├── README.md               ← Visão geral dos scripts
│   ├── windows/                ← Scripts .bat / .ps1 para Windows
│   │   ├── dev-all.bat
│   │   ├── dev-backend.bat
│   │   ├── dev-frontend.bat
│   │   ├── dev-whatsapp.bat
│   │   ├── run-backend.bat
│   │   ├── run-frontend.bat
│   │   ├── run-whatsapp.bat
│   │   └── README.md
│   └── dev/                    ← Scripts utilitários
│       ├── seed_sheets.py
│       ├── setup.sh
│       └── README.md
│
├── docs/                       ← Documentação
│   ├── README.md
│   ├── ARCHITECTURE.md
│   ├── GOOGLE_SHEETS_SETUP.md
│   ├── OPERACAO.md
│   ├── WHATSAPP_SETUP.md
│   └── reports/JULES_REPORT.md
│
├── backend/                    ← API FastAPI (Python)
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   ├── scripts/                ← Scripts internos (bootstrap, admin)
│   ├── src/
│   │   ├── api/               ← Rotas FastAPI
│   │   ├── application/       ← Casos de uso, serviços
│   │   ├── domain/            ← Entidades, value objects
│   │   └── infrastructure/    ← Banco, cache, IA, sheets
│   └── tests/
│
├── frontend/                   ← Aplicação React (Vite)
│   ├── Dockerfile
│   ├── vite.config.mjs
│   ├── src/
│   └── public/
│
├── whatsapp-service/           ← Serviço WhatsApp (Node.js)
│   ├── Dockerfile
│   └── src/
│
└── shared/media/               ← Mídia compartilhada (volumes)
```

## Requisitos

### Desenvolvimento Local

- **Python** ≥ 3.11
- **Node.js** ≥ 18
- **Redis** (para Celery — opcional em dev sem tarefas assíncronas)
- **Ollama** (opcional — necessário apenas para OCR/IA)
- **Git**

### Produção (Docker)

- **Docker** ≥ 24
- **Docker Compose** ≥ 2.20

## Instalação

```bash
# Clone o repositório
git clone https://github.com/aganimoto/comunhaodebens.git
cd comunhaodebens

# Configure as variáveis de ambiente
cp config/.env.example .env

# Backend (Python)
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -e ".[dev]"

# Frontend
cd ../frontend
npm install

# WhatsApp Service
cd ../whatsapp-service
npm install
```

## Configuração

### Variáveis de Ambiente

Copie `config/.env.example` para `.env` na raiz e ajuste:

| Variável | Descrição | Exemplo (dev) |
|---|---|---|
| `DATABASE_URL` | Conexão com banco de dados | `sqlite+aiosqlite:///...` |
| `JWT_SECRET_KEY` | Chave secreta JWT (mude em prod!) | `dev-jwt-secret-...` |
| `CORS_ORIGINS` | Origens permitidas (CORS) | `http://localhost:5173` |
| `WHATSAPP_SERVICE_URL` | URL do WhatsApp Service | `http://localhost:3000` |
| `OLLAMA_BASE_URL` | URL do servidor Ollama | `http://localhost:11434` |
| `GOOGLE_SPREADSHEET_ID` | ID da planilha Google Sheets | (opcional em dev) |

Consulte `config/README.md` e `backend/src/config.py` para a lista completa.

## Como Executar

### Desenvolvimento (Windows)

Use o script `dev-all.bat` que inicia todos os serviços em terminais separados:

```cmd
scripts\windows\dev-all.bat
```

Ou inicie individualmente:

```cmd
scripts\windows\run-backend.bat    # Backend :8000
scripts\windows\run-frontend.bat   # Frontend :5173
scripts\windows\run-whatsapp.bat   # WhatsApp :3000
```

### Desenvolvimento (Linux/Mac)

```bash
# Terminal 1 - Backend
cd backend
pip install -e ".[dev]"
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend
cd frontend
npm run dev

# Terminal 3 - WhatsApp Service
cd whatsapp-service
node src/index.js
```

### Produção (Docker)

```bash
# Build e start
docker compose -f infra/docker/docker-compose.yml up -d --build

# Acompanhar logs
docker compose -f infra/docker/docker-compose.yml logs -f
```

## Fluxo dos Scripts .bat

### `dev-all.bat`

1. Cria diretórios `dev_data/media`, `dev_data/relatorios`, `dev_data/backups`
2. Se banco SQLite não existe, executa `bootstrap_local_db.py` + `create_admin.py`
3. Abre 4 terminais:
   - **Backend API** — `uvicorn` na porta 8000
   - **Celery Worker** — processa tarefas assíncronas
   - **WhatsApp Service** — `node src/index.js` na porta 3000
   - **Frontend** — `npm run dev` na porta 5173

### Scripts Individuais

- `run-backend.bat` — executa apenas o backend (útil para debug com logs concentrados)
- `run-frontend.bat` — executa apenas o frontend
- `run-whatsapp.bat` — executa apenas o WhatsApp Service

> **Nota:** Todos os scripts usam caminhos relativos (`%~dp0..\..`) e funcionam de qualquer diretório.

## Solução de Problemas Comuns

| Problema | Causa | Solução |
|---|---|---|
| `ECONNREFUSED` no frontend | Backend não está rodando | Execute `run-backend.bat` |
| `unable to open database file` | Caminho do SQLite inválido | Use caminho com `/` (não `\`) na URL |
| `Execution context was destroyed` | Reconexão do WhatsApp Web | O sistema tenta novamente automaticamente (3x) |
| `auth timeout` | Sessão WhatsApp expirou | Limpe `.wwebjs_auth` e reconecte |
| Celery não conecta | Redis não está rodando | Inicie Redis ou ignore se não usar tarefas |
| Google Sheets não conecta | Service account não configurada | Configure `GOOGLE_SERVICE_ACCOUNT_JSON` |

## Variáveis de Ambiente

Veja `config/.env.example` para a lista completa com valores padrão de desenvolvimento.

## Checklist de Deploy

- [ ] Alterar `JWT_SECRET_KEY` para uma chave forte e secreta
- [ ] Alterar `WHATSAPP_WEBHOOK_SECRET` para um valor seguro
- [ ] Configurar `DATABASE_URL` para PostgreSQL (produção)
- [ ] Configurar `CORS_ORIGINS` com domínio real
- [ ] Configurar `GOOGLE_SERVICE_ACCOUNT_JSON` com service account real
- [ ] Configurar `GOOGLE_SPREADSHEET_ID` com ID da planilha
- [ ] Ajustar `OLLAMA_BASE_URL` se Ollama estiver em servidor diferente
- [ ] Verificar variável `DEV_MODE=false`
- [ ] Buildar imagens Docker com `docker compose build`
- [ ] Executar migrações: `alembic upgrade head`
- [ ] Criar admin inicial: `python scripts/create_admin.py`
- [ ] Configurar backup automático do banco
- [ ] Verificar logs de todos os serviços
- [ ] Testar recebimento de mensagem WhatsApp
- [ ] Testar sincronização Google Sheets