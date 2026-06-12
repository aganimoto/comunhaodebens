# 🕊️ CDB Shalom

**Comunidade Católica Shalom** — Sistema de gestão de contribuições e comunicação via WhatsApp.

> Automatize o recebimento, processamento e gestão de comprovantes de contribuição dos membros da comunidade através do WhatsApp, com extração inteligente de dados via OCR + regex e sincronização com Google Sheets.

---

## 📋 Índice

- [Funcionalidades](#-funcionalidades)
- [Arquitetura](#-arquitetura)
- [Stack Tecnológica](#-stack-tecnológica)
- [Pré-requisitos](#-pré-requisitos)
- [Setup Rápido (Desenvolvimento Local)](#-setup-rápido-desenvolvimento-local)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
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
| 📱 **Recebimento via WhatsApp** | Membros enviam fotos de comprovantes e o sistema processa automaticamente |
| 🤖 **OCR Local** | Extrai texto de comprovantes usando **EasyOCR** — sem depender de APIs externas |
| 📊 **Google Sheets** | Persistência de dados em planilha Google Sheets (único banco de dados) |
| 📈 **Dashboard Admin** | Métricas, pendências, relatórios gráficos e gestão de membros |
| 📄 **Relatórios Mensais** | Geração automática de PDFs com distribuição via WhatsApp |
| 🔐 **Autenticação JWT** | Controle de acesso por perfil: `administrador`, `financeiro`, `consulta` |
| 🧠 **Extração Inteligente** | Regex otimizadas para extrair valor, data e favorecido de comprovantes |
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
             │ 📊 Sheets│ │ ⚡ Redis │ │ 🧠 Ollama│
             │ Google   │ │ (Celery  │ │ (IA      │
             │ (único   │ │  broker) │ │  local)  │
             │  banco)  │ │          │ │          │
             └──────────┘ └──────────┘ └──────────┘
```

### Fluxo de Dados

```
Membro → WhatsApp → WhatsApp Service → Webhook → Backend API
                                                     │
                                          ┌──────────┴──────────┐
                                          ▼                     ▼
                                     EasyOCR + Regex      Google Sheets
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
| **Python** | ≥ 3.12 | Linguagem principal |
| **FastAPI** | 0.115+ | Framework REST assíncrono |
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

### Infraestrutura
| Tecnologia | Finalidade |
|---|---|
| **Docker + Compose** | Containerização |
| **Google Sheets** | Banco de dados principal |
| **Redis** | Cache / Celery broker |
| **Ollama** | IA local (llama3.2:1b) |
| **Nginx (proxy)** | Reverse proxy (produção) |

---

## 📦 Pré-requisitos

### Desenvolvimento Local
- **Python** ≥ 3.12
- **Node.js** ≥ 18
- **npm** ≥ 9
- **Git
- **Redis** (opcional — apenas se usar tarefas assíncronas)
- **Ollama** com modelo `llama3.2:1b` (opcional — necessário apenas para classificação)

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

### 2. Configurar Google Sheets

1. Crie uma **Service Account** no Google Cloud Console
2. Baixe o JSON da service account
3. Configure `GOOGLE_SERVICE_ACCOUNT_JSON` no `.env` com o caminho do arquivo
4. Configure `GOOGLE_SPREADSHEET_ID` com o ID da sua planilha
5. Compartilhe a planilha com o e-mail da service account (permissão editor)

### 3. Backend

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

# Inicie o servidor
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Frontend

```bash
cd frontend

# Instale as dependências
npm install

# Inicie o servidor de desenvolvimento
npm run dev
```

> O frontend rodará em **http://localhost:5173**.

### 5. WhatsApp Service

```bash
cd whatsapp-service
npm install
npm start
```

> O serviço rodará em **http://localhost:3000**.

---

## 🔐 Variáveis de Ambiente

| Variável | Descrição | Exemplo |
|---|---|---|
| `JWT_SECRET_KEY` | Chave secreta JWT | `dev-jwt-secret-change-me-64-chars...` |
| `CORS_ORIGINS` | Origens permitidas (CORS) | `http://localhost:5173` |
| `WHATSAPP_SERVICE_URL` | URL do WhatsApp Service | `http://localhost:3000` |
| `OLLAMA_BASE_URL` | URL do servidor Ollama | `http://localhost:11434` |
| `OLLAMA_MODEL` | Modelo de IA para classificação | `llama3.2:1b` |
| `OCR_ENGINE` | Engine de OCR | `easyocr` (recomendado) |
| `GOOGLE_SPREADSHEET_ID` | ID da planilha Google | *(obrigatório)* |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Caminho para JSON da service account | *(obrigatório)* |
| `APP_TIMEZONE` | Fuso horário | `America/Sao_Paulo` |

> Consulte [`config/.env.example`](config/.env.example) para a lista completa.

---

## 🪟 Scripts Windows (.bat)

O projeto inclui scripts prontos para Windows na pasta `scripts/windows/`:

### `dev-all.bat` — Inicia tudo de uma vez

```cmd
scripts\windows\dev-all.bat
```

Este script:
1. Cria os diretórios necessários
2. Abre **3 terminais** automaticamente:
   - **Backend API** — `uvicorn` na porta **8000**
   - **WhatsApp Service** — `node` na porta **3000**
   - **Frontend** — `npm run dev` na porta **5173**

### Scripts Individuais

```cmd
scripts\windows\run-backend.bat    # Backend :8000
scripts\windows\run-frontend.bat   # Frontend :5173
scripts\windows\run-whatsapp.bat   # WhatsApp :3000
```

---

## 🐳 Docker (Produção)

```bash
# Build e start todos os serviços
docker compose -f infra/docker/docker-compose.yml up -d --build

# Acompanhar logs
docker compose -f infra/docker/docker-compose.yml logs -f

# Parar serviços
docker compose -f infra/docker/docker-compose.yml down
```

### Serviços Docker

| Serviço | Porta | Descrição |
|---|---|---|
| `backend` | `8000` | API FastAPI |
| `frontend` | `5173` | App React (Vite) |
| `whatsapp-service` | `3000` | Serviço WhatsApp |
| `redis` | `6379` | Cache / Celery broker |
| `ollama` | `11434` | IA local (llama3.2:1b) |

---

## 📚 Documentação

A documentação completa está na pasta [`docs/`](docs/):

| Documento | Conteúdo |
|---|---|
| [📖 Arquitetura](docs/ARCHITECTURE.md) | Detalhamento técnico da arquitetura |
| [📊 Google Sheets Setup](docs/GOOGLE_SHEETS_SETUP.md) | Configuração de service account e planilhas |
| [💬 WhatsApp Setup](docs/WHATSAPP_SETUP.md) | Configuração do WhatsApp Web |
| [⚙️ Operação](docs/OPERACAO.md) | Rotinas operacionais e troubleshooting |

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
│       └── ollama/Modelfile
│
├── scripts/
│   ├── windows/                     ← Scripts .bat para Windows
│   │   ├── dev-all.bat
│   │   ├── run-backend.bat
│   │   ├── run-frontend.bat
│   │   └── run-whatsapp.bat
│   └── dev/                         ← Scripts utilitários
│       └── seed_sheets.py
│
├── docs/                            ← Documentação
│   ├── ARCHITECTURE.md
│   ├── GOOGLE_SHEETS_SETUP.md
│   ├── OPERACAO.md
│   └── WHATSAPP_SETUP.md
│
├── backend/                         ← API FastAPI (Python)
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── src/
│       ├── api/                     ← Rotas FastAPI
│       ├── application/             ← Casos de uso, serviços
│       ├── domain/                  ← Entidades (enums), value objects
│       └── infrastructure/          ← Cache, IA (Ollama), Sheets
│
├── frontend/                        ← Aplicação React (Vite)
│   ├── .env.development
│   ├── vite.config.mjs
│   └── src/
│
├── whatsapp-service/                ← Serviço WhatsApp (Node.js)
│   ├── Dockerfile
│   └── src/
│
├── test_ocr/                        ← Testes de OCR
│   └── executar_teste_final.py
│
└── shared/media/                    ← Mídia compartilhada (volumes Docker)
```

---

## 🔧 Solução de Problemas

| Problema | Causa | Solução |
|---|---|---|
| `ECONNREFUSED` no frontend | Backend não está rodando | Execute `run-backend.bat` ou `uvicorn` |
| Google Sheets não conecta | Service account não configurada | Configure `GOOGLE_SERVICE_ACCOUNT_JSON` e `GOOGLE_SPREADSHEET_ID` |
| `ModuleNotFoundError` | Dependências não instaladas | `pip install -e ".[dev]"` |
| OCR não funciona | EasyOCR não instalado | Execute `python -c "import easyocr; easyocr.Reader(['pt'])"` |
| `Porta já em uso` | Outro processo na mesma porta | Mude a porta ou mate o processo |
| Celery não conecta | Redis não está rodando | Inicie Redis ou ignore se não usar tarefas assíncronas |

---

## ✅ Checklist de Deploy

- [ ] Alterar `JWT_SECRET_KEY` para uma chave forte e secreta (mín. 64 caracteres)
- [ ] Alterar `WHATSAPP_WEBHOOK_SECRET` para um valor seguro
- [ ] Alterar `BOOTSTRAP_ADMIN_PASSWORD` para uma senha forte
- [ ] Configurar `GOOGLE_SERVICE_ACCOUNT_JSON` com service account real
- [ ] Configurar `GOOGLE_SPREADSHEET_ID` com ID da planilha
- [ ] Compartilhar planilha com e-mail da service account
- [ ] Configurar `OLLAMA_BASE_URL` se Ollama estiver em servidor diferente
- [ ] Executar `ollama pull llama3.2:1b` para baixar o modelo
- [ ] Verificar variável `DEV_MODE=false`
- [ ] Configurar backup automático do banco (Google Sheets)
- [ ] Verificar logs de todos os serviços
- [ ] Testar recebimento de mensagem WhatsApp
- [ ] Testar sincronização Google Sheets
- [ ] Configurar HTTPS (recomendado: Traefik ou Nginx + Let's Encrypt)

---

## 📄 Licença

Projeto privado — **Comunidade Católica Shalom**.

---

<p align="center">Feito com ❤️ para a Comunidade Católica Shalom</p>