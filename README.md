# 🕊️ CDB Shalom

**Comunidade Católica Shalom** — Sistema de gestão de contribuições e comunicação via WhatsApp.

> Automatize o recebimento, processamento e gestão de comprovantes de contribuição dos membros da comunidade através do WhatsApp, com extração inteligente de dados via OCR + IA local e sincronização com Google Sheets.

---

## 📋 Índice

- [Funcionalidades](#-funcionalidades)
- [Arquitetura](#-arquitetura)
- [Stack Tecnológica](#-stack-tecnológica)
- [Pré-requisitos](#-pré-requisitos)
- [Setup Rápido (Desenvolvimento Local)](#-setup-rápido-desenvolvimento-local)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
- [Senhas e Credenciais para Teste](#-senhas-e-credenciais-para-teste)
- [Scripts Windows (.bat)](#-scripts-windows-bat)
- [Docker (Produção)](#-docker-produção)
- [Documentação](#-documentação)
- [Estrutura de Diretórios](#-estrutura-de-diretórios)
- [Solução de Problemas](#-solução-de-problemas)
- [Checklist de Deploy](#-checklist-de-deploy)

---

## ✨ Funcionalidades

| Funcionalidade | Descrição |
|---|---|
| 📱 **Recebimento via WhatsApp** | Membros enviam fotos/extratos de comprovantes e o sistema processa automaticamente |
| 🤖 **OCR + IA Local** | Extrai dados de comprovantes usando **EasyOCR** + **Ollama (LLaVA/Qwen VL)** — sem depender de APIs externas |
| 📊 **Google Sheets** | Sincronização bidirecional em tempo real com planilhas |
| 📈 **Dashboard Admin** | Métricas, pendências, relatórios gráficos e gestão de membros |
| 📄 **Relatórios Mensais** | Geração automática de PDFs com distribuição via WhatsApp |
| 🔐 **Autenticação JWT** | Controle de acesso por perfil: `administrador`, `financeiro`, `consulta` |
| 🧠 **Fallback Inteligente** | Múltiplos modelos de IA em cascata para garantir robustez na leitura |
| 📦 **Containerizado** | Docker Compose full-stack pronto para produção |

---

## 🏗 Arquitetura

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   🌐 Frontend   │────▶│   ⚙️ Backend     │────▶│   💬 WhatsApp   │
│  (Vite + React) │◀────│   (FastAPI)       │◀────│   Service       │
│     :5173       │     │     :8000         │     │   :3000         │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
             ┌──────────┐ ┌──────────┐ ┌──────────┐
             │ 🗄️ BD    │ │ ⚡ Redis │ │ 🧠 Ollama│
             │PostgreSQL│ │ (Celery  │ │ (IA      │
             │(SQLite em│ │  broker) │ │  local)  │
             │  dev)    │ │          │ │          │
             └──────────┘ └──────────┘ └──────────┘
```

### Fluxo de Dados

```
Membro → WhatsApp → WhatsApp Service → Webhook → Backend API
                                                     │
                                          ┌──────────┴──────────┐
                                          ▼                     ▼
                                     EasyOCR + Ollama      Google Sheets
                                          │                     │
                                          ▼                     ▼
                                     Extração de Dados    Planilha Atualizada
                                          │
                                          ▼
                                     Dashboard Admin
```

---

## 🛠 Stack Tecnológica

### Backend
| Tecnologia | Versão | Finalidade |
|---|---|---|
| **Python** | ≥ 3.11 | Linguagem principal |
| **FastAPI** | 0.115+ | Framework REST assíncrono |
| **SQLAlchemy** | 2.0+ | ORM assíncrono |
| **Alembic** | 1.13+ | Migrações de banco |
| **Celery** | 5.4+ | Tarefas assíncronas (opcional em dev) |
| **EasyOCR** | 1.7+ | OCR local (deep learning) |
| **Pydantic** | 2.x | Validação de schemas |

### Frontend
| Tecnologia | Finalidade |
|---|---|
| **React 19** | UI components |
| **Vite 6** | Build tool / dev server |
| **TypeScript** | Type safety |
| **Tailwind CSS** | Estilização |
| **TanStack Router** | Roteamento |
| **TanStack Query** | Server state / cache |
| **shadcn/ui** | Componentes de design system |
| **Recharts** | Gráficos do dashboard |
| **React Hook Form** | Formulários |

### Infraestrutura
| Tecnologia | Finalidade |
|---|---|
| **Docker + Compose** | Containerização |
| **PostgreSQL** | Banco de dados (produção) |
| **SQLite** | Banco de dados (desenvolvimento) |
| **Redis** | Cache / Celery broker |
| **Ollama** | IA local (LLaVA / Qwen VL) |
| **Nginx (proxy)** | Reverse proxy (produção) |

---

## 📦 Pré-requisitos

### Desenvolvimento Local
- **Python** ≥ 3.11
- **Node.js** ≥ 18
- **npm** ≥ 9
- **Git**
- **Redis** (opcional — apenas se for usar tarefas assíncronas)
- **Ollama** (opcional — necessário apenas para OCR com IA; EasyOCR funciona sem)

### Produção (Docker)
- **Docker** ≥ 24
- **Docker Compose** ≥ 2.20

---

## 🚀 Setup Rápido (Desenvolvimento Local)

### 1. Clone e configure

```bash
git clone https://github.com/aganimoto/comunhaodebens.git
cd comunhaodebens

# Configure as variáveis de ambiente
cp config/.env.example .env
```

### 2. Backend

```bash
cd backend

# Crie o virtual environment
python -m venv .venv

# Ative (Windows)
.venv\Scripts\activate
# Ative (Linux/Mac)
# source .venv/bin/activate

# Instale com dependências de dev
pip install -e ".[dev]"

# Execute as migrações do banco
alembic upgrade head

# Crie o usuário admin padrão
python scripts/create_admin.py

# Inicie o servidor
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend

```bash
cd frontend

# Instale as dependências
npm install

# Inicie o servidor de desenvolvimento
npm run dev
```

> O frontend rodará em **http://localhost:5173**.
> O Vite está configurado com proxy (`/api` → `localhost:8000`), então não há problemas de CORS em desenvolvimento.

### 4. WhatsApp Service

```bash
cd whatsapp-service
npm install
npm start
```

> O serviço rodará em **http://localhost:3000**.

---

## 🔐 Variáveis de Ambiente

| Variável | Descrição | Exemplo (dev) |
|---|---|---|
| `DATABASE_URL` | Conexão com banco de dados | `sqlite+aiosqlite:///./dev_data/local.db` |
| `JWT_SECRET_KEY` | Chave secreta JWT | `dev-jwt-secret-change-me-64-chars...` |
| `CORS_ORIGINS` | Origens permitidas (CORS) | `http://localhost:5173` |
| `WHATSAPP_SERVICE_URL` | URL do WhatsApp Service | `http://localhost:3000` |
| `OLLAMA_BASE_URL` | URL do servidor Ollama | `http://localhost:11434` |
| `OCR_ENGINE` | Engine de OCR | `easyocr` (recomendado) |
| `GOOGLE_SPREADSHEET_ID` | ID da planilha Google | *(opcional em dev)* |
| `APP_TIMEZONE` | Fuso horário | `America/Sao_Paulo` |
| `DEV_MODE` | Modo desenvolvimento | `true` |

> Consulte [`config/.env.example`](config/.env.example) e [`config/README.md`](config/README.md) para a lista completa.

---

## 🔑 Senhas e Credenciais para Teste

### Admin Local (criado pelo script `create_admin.py`)

| Campo | Valor |
|---|---|
| **E-mail** | `admin@cdbshalom.local` |
| **Senha** | `TroqueEstaSenha123!` |
| **Perfil** | `administrador` |

> ⚠️ Esta é a senha **default de desenvolvimento**, definida em `backend/src/config.py`. Em produção, **ALTERE** via variável de ambiente `BOOTSTRAP_ADMIN_PASSWORD`.

### Frontend (.env.development)

| Configuração | Valor |
|---|---|
| `VITE_API_BASE_URL` | `/api/v1` (proxy Vite → backend) |
| URL de acesso | `http://localhost:5173` |

### Configuração do Banco (dev)

O banco SQLite local é criado automaticamente em:

```
backend/dev_data/local.db
```

### Credenciais Docker (produção)

| Serviço | Usuário | Senha (default) |
|---|---|---|
| PostgreSQL | `cdb_user` | `CHANGE_ME` (definir em `.env`) |
| Redis | — | Sem autenticação (apenas rede interna) |

---

## 🪟 Scripts Windows (.bat)

O projeto inclui scripts prontos para Windows na pasta `scripts/windows/`:

### `dev-all.bat` — Inicia tudo de uma vez

```cmd
scripts\windows\dev-all.bat
```

Este script:
1. Cria os diretórios `dev_data/media`, `dev_data/relatorios`, `dev_data/backups`
2. Se o banco SQLite não existir, executa `alembic upgrade head`
3. Abre **3 terminais** automaticamente:
   - **Backend API** — `uvicorn` na porta **8000**
   - **WhatsApp Service** — `node` na porta **3000**
   - **Frontend** — `npm run dev` na porta **5173**

### Scripts Individuais

```cmd
scripts\windows\run-backend.bat    # Backend :8000
scripts\windows\run-frontend.bat   # Frontend :5173
scripts\windows\run-whatsapp.bat   # WhatsApp :3000
```

> Todos os scripts usam caminhos relativos e funcionam de qualquer diretório.

---

## 🐳 Docker (Produção)

```bash
# Build e start todos os serviços
docker compose -f infra/docker/docker-compose.yml up -d --build

# Acompanhar logs
docker compose -f infra/docker/docker-compose.yml logs -f

# Parar serviços
docker compose -f infra/docker/docker-compose.yml down

# Executar migrações
docker compose exec backend alembic upgrade head

# Criar admin
docker compose exec backend python scripts/create_admin.py
```

### Serviços Docker

| Serviço | Porta | Descrição |
|---|---|---|
| `backend` | `8000` | API FastAPI |
| `frontend` | `5173` | App React (Vite) |
| `whatsapp-service` | `3000` | Serviço WhatsApp |
| `postgres` | `5432` | Banco de dados |
| `redis` | `6379` | Cache / Celery broker |
| `ollama` | `11434` | IA local |

---

## 📚 Documentação

A documentação completa está na pasta [`docs/`](docs/):

| Documento | Conteúdo |
|---|---|
| [📖 Arquitetura](docs/ARCHITECTURE.md) | Detalhamento técnico da arquitetura, decisões de design, fluxos |
| [📊 Google Sheets Setup](docs/GOOGLE_SHEETS_SETUP.md) | Configuração de service account, permissões, estrutura de planilhas |
| [💬 WhatsApp Setup](docs/WHATSAPP_SETUP.md) | Configuração do WhatsApp Web, webhooks, tratamento de mensagens |
| [⚙️ Operação](docs/OPERACAO.md) | Rotinas operacionais, backup, manutenção, troubleshooting |
| [🧪 Testes OCR](test_ocr/README.md) | Resultados e metodologia dos testes de OCR |
| [🔧 Scripts](scripts/README.md) | Visão geral de todos os scripts disponíveis |

### API Docs (Swagger)

Com o backend rodando, acesse:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 📁 Estrutura de Diretórios

```
comunhaodebens/
├── README.md
├── .gitignore
│
├── config/                          ← Variáveis de ambiente
│   ├── .env.example
│   └── README.md
│
├── infra/
│   └── docker/                      ← Docker Compose e configurações
│       ├── docker-compose.yml
│       ├── docker-compose.dev.yml
│       ├── ollama/Modelfile
│       └── README.md
│
├── scripts/
│   ├── README.md
│   ├── windows/                     ← Scripts .bat / .ps1 para Windows
│   │   ├── dev-all.bat
│   │   ├── run-backend.bat
│   │   ├── run-frontend.bat
│   │   ├── run-whatsapp.bat
│   │   └── README.md
│   └── dev/                         ← Scripts utilitários
│       ├── seed_sheets.py
│       ├── setup.sh
│       └── README.md
│
├── docs/                            ← Documentação
│   ├── README.md
│   ├── ARCHITECTURE.md
│   ├── GOOGLE_SHEETS_SETUP.md
│   ├── OPERACAO.md
│   ├── WHATSAPP_SETUP.md
│   └── reports/JULES_REPORT.md
│
├── backend/                         ← API FastAPI (Python)
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   ├── scripts/
│   ├── src/
│   │   ├── api/                     ← Rotas FastAPI
│   │   ├── application/             ← Casos de uso, serviços
│   │   ├── domain/                  ← Entidades, value objects
│   │   └── infrastructure/          ← Banco, cache, IA, sheets
│   └── tests/
│
├── frontend/                        ← Aplicação React (Vite)
│   ├── .env.development
│   ├── Dockerfile
│   ├── vite.config.mjs
│   ├── src/
│   └── public/
│
├── whatsapp-service/                ← Serviço WhatsApp (Node.js)
│   ├── Dockerfile
│   └── src/
│
├── test_ocr/                        ← Testes de OCR
│   ├── executar_teste_final.py
│   ├── teste_fluxo_completo.py
│   ├── README.md
│   └── RESULTADOS_COMPLETOS.md
│
└── shared/media/                    ← Mídia compartilhada (volumes Docker)
```

---

## 🔧 Solução de Problemas

| Problema | Causa | Solução |
|---|---|---|
| `ECONNREFUSED` no frontend | Backend não está rodando | Execute `run-backend.bat` ou `uvicorn` |
| `unable to open database file` | Caminho SQLite inválido | Use caminho com `/` (não `\`) na URL |
| `Execution context was destroyed` | Reconexão WhatsApp Web | O sistema tenta novamente automaticamente (3x) |
| `auth timeout` | Sessão WhatsApp expirou | Limpe `.wwebjs_auth` e reconecte |
| Celery não conecta | Redis não está rodando | Inicie Redis ou ignore se não usar tarefas assíncronas |
| Google Sheets não conecta | Service account não configurada | Configure `GOOGLE_SERVICE_ACCOUNT_JSON` |
| `ModuleNotFoundError` | Dependências não instaladas | `pip install -e ".[dev]"` |
| OCR não funciona | EasyOCR não instalado / modelo não baixado | Execute `python -c "import easyocr; easyocr.Reader(['pt'])"` para baixar modelos |
| `Porta já em uso` | Outro processo na mesma porta | Mude a porta ou mate o processo: `netstat -ano \| findstr :8000` |

---

## ✅ Checklist de Deploy

- [ ] Alterar `JWT_SECRET_KEY` para uma chave forte e secreta (mín. 64 caracteres)
- [ ] Alterar `WHATSAPP_WEBHOOK_SECRET` para um valor seguro
- [ ] Alterar `BOOTSTRAP_ADMIN_PASSWORD` para uma senha forte
- [ ] Configurar `DATABASE_URL` para PostgreSQL (produção)
- [ ] Configurar `CORS_ORIGINS` com domínio real
- [ ] Configurar `GOOGLE_SERVICE_ACCOUNT_JSON` com service account real
- [ ] Configurar `GOOGLE_SPREADSHEET_ID` com ID da planilha
- [ ] Ajustar `OLLAMA_BASE_URL` se Ollama estiver em servidor diferente
- [ ] Ajustar `POSTGRES_PASSWORD` para uma senha forte
- [ ] Verificar variável `DEV_MODE=false`
- [ ] Buildar imagens Docker com `docker compose build`
- [ ] Executar migrações: `alembic upgrade head`
- [ ] Criar admin inicial: `python scripts/create_admin.py`
- [ ] Configurar backup automático do banco
- [ ] Verificar logs de todos os serviços
- [ ] Testar recebimento de mensagem WhatsApp
- [ ] Testar sincronização Google Sheets
- [ ] Configurar HTTPS (recomendado: Traefik ou Nginx + Let's Encrypt)

---

## 📄 Licença

Projeto privado — **Comunidade Católica Shalom**.

---

<p align="center">Feito com ❤️ para a Comunidade Católica Shalom</p>