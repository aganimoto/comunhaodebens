# CDB Shalom — Comunhão de Bens

Sistema local (on-premise) para automatizar o recebimento e registro de contribuições PIX enviadas por comprovante no **WhatsApp**, com operação diária via **Google Sheets**.

## Regra central

A identidade do contribuinte é definida **somente** pelo número de WhatsApp cadastrado na aba **Membros**. A IA extrai apenas valor, data, hora e banco — nunca nome ou categoria.

## Stack

| Camada | Tecnologia |
|--------|------------|
| Backend | Python 3.12, FastAPI, SQLAlchemy, Celery, WeasyPrint |
| Banco | PostgreSQL 16 |
| Fila/cache | Redis 7 |
| OCR / IA | PaddleOCR, Ollama (qwen2.5-vl) |
| WhatsApp | Node.js, whatsapp-web.js |
| Admin | React 18, Vite, Tailwind, shadcn/ui |
| Planilha | Google Sheets API |
| Testes | pytest, fakeredis, testcontainers |

## Início rápido (produção)

### 1. Configurar ambiente

```bash
cp .env.example .env
# Edite senhas, GOOGLE_SPREADSHEET_ID, JWT_SECRET_KEY, WHATSAPP_WEBHOOK_SECRET
mkdir -p secrets
# Coloque a service account em secrets/google_sa.json
```

### 2. Subir serviços

```bash
docker compose up -d
docker compose exec backend alembic upgrade head
```

### 3. Criar o primeiro administrador

```bash
docker compose exec backend python scripts/create_admin.py
# ou com parâmetros próprios:
docker compose exec backend python scripts/create_admin.py \
    --email admin@cdbshalom.org --senha 'SenhaForte123!' --perfil administrador
```

### 4. Planilha Google

```bash
docker compose exec backend python scripts/seed_sheets.py
```

Cadastre membros na aba **Membros** (telefone sem `+`, ex.: `5511999999999`).

### 5. WhatsApp

```bash
docker compose logs -f whatsapp-service
```

Ou acesse a página **WhatsApp** no painel admin (`/whatsapp`) para escanear o QR Code diretamente pelo navegador. Detalhes em [docs/WHATSAPP_SETUP.md](docs/WHATSAPP_SETUP.md).

### 6. Painel admin

- Produção: <http://localhost:5173>
- API: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health/ready>

## Modo DEV (sem Google/WhatsApp/Ollama)

O modo dev substitui todas as integrações externas por mocks em memória, ideal para desenvolvimento local e para a equipe testar o painel sem precisar configurar nada.

### Subir o stack em modo dev

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Sem Docker (Windows / macOS — SQLite local)

Quando o Docker não estiver instalado, é possível rodar o backend com mocks em SQLite.
A documentação detalhada do fluxo local está em [`scripts/dev-backend-local.ps1`](scripts/dev-backend-local.ps1).

**Pré-requisitos:** Python 3.12+, Node.js 18+.

#### Setup inicial (primeira vez)

```powershell
# 1. Backend — instalar dependências e criar banco
cd backend
pip install -e .
python scripts/bootstrap_local_db.py   # cria SQLite e aplica migrations
python scripts/create_admin.py         # cria primeiro admin (admin@cdbshalom.local / TroqueEstaSenha123!)
cd ..

# 2. Frontend — instalar dependências
cd frontend
npm install
cd ..
```

#### Iniciar o ambiente (todo dia)

Abrir **três terminais** na raiz do projeto:

**Terminal 1 — API:**

```powershell
.\scripts\dev-backend-local.ps1
# Seta DEV_MODE=true, DATABASE_URL (SQLite), JWT_SECRET_KEY, etc.
# Sobe uvicorn em http://localhost:8000 com --reload
```

**Terminal 2 — WhatsApp Service (Node.js):**

```powershell
cd whatsapp-service
$env:PORT = "3000"
$env:WHATSAPP_WEBHOOK_URL = "http://localhost:8000/api/v1/webhooks/whatsapp"
$env:WHATSAPP_WEBHOOK_SECRET = "dev-webhook-secret-32-chars-long!!"
$env:SHARED_MEDIA_PATH = "../shared/media"
npm install
npm run dev
# Escaneie o QR Code exibido no terminal
```

> **Nota:** o WhatsApp service requer Google Chrome/Chromium instalado (usa Puppeteer). Se o `npm run dev` falhar, verifique se o Chrome está acessível ou defina `PUPPETEER_EXECUTABLE_PATH` para o caminho do seu Chrome.

**Terminal 3 — Painel admin:**

```powershell
cd frontend
npm run dev
# Vite em http://localhost:5173 com proxy /api → localhost:8000
```

#### URLs de acesso

| Serviço | URL |
|---------|-----|
| API (Swagger) | <http://localhost:8000/docs> |
| Painel admin | <http://localhost:5173> |
| WhatsApp (QR Code) | <http://localhost:5173/whatsapp> |
| Health check | <http://localhost:8000/health/ready> |

> **Recomendação:** para o ambiente completo (Postgres, Celery, WhatsApp), instale o Docker Desktop e use `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` conforme a seção [Modo DEV](#modo-dev-sem-googlewhatsappollama) acima.

### O que muda em `DEV_MODE=true`

- **Google Sheets** → usa a planilha real (requer `GOOGLE_SPREADSHEET_ID` e `GOOGLE_SERVICE_ACCOUNT_JSON` no `.env`). Para usar o mock, defina `DEV_USE_REAL_SHEETS=false`.
- **Ollama (IA)** → parser determinístico a partir de qualquer entrada
- **WhatsApp Service** → mensagens gravadas em `backend/dev_data/whatsapp_outbox.json` (status retorna `connected` automaticamente)
- **pg_dump** → gera placeholder em `backend/dev_data/backups/`
- **Relatórios PDF** → salvos em `backend/dev_data/relatorios/`

### Popular dados de exemplo

```bash
docker compose exec backend python scripts/seed_dev_data.py
# Cria 5 membros, 20 contribuições dos últimos 45 dias e 2 pendências
```

### Credenciais padrão do admin dev

- e-mail: `admin@cdbshalom.local`
- senha: `TroqueEstaSenha123!`

## Testes

### Cobertura local (sem Docker)

```bash
docker compose exec backend pip install -e ".[dev]"
docker compose exec backend pytest
# Cobertura é gerada em backend/htmlcov/index.html
```

### Testes de integração com testcontainers (requer Docker)

```bash
docker compose exec backend pytest -m integration
```

## Funcionalidades implementadas (fases 5–6)

- **Relatório PDF mensal** (WeasyPrint) gerado automaticamente todo dia 1º às 06:00 via Celery Beat
- **Backup real com pg_dump** diário às 02:00, com rotação dos últimos 30 arquivos
- **shadcn/ui completo** no frontend (Button, Card, Input, Label, Table, Dialog, Toast, Badge)
- **Cobertura ≥ 80%** com pytest + coverage (relatórios em `htmlcov/`)
- **Testes de integração** com testcontainers (Postgres + Redis)
- **Modo DEV** com mocks determinísticos (Sheets/Ollama/WhatsApp/pg_dump)
- **Script `create_admin`** idempotente para o primeiro usuário
- **Toasts** para feedback imediato em ações do painel
- **Filtros e busca** na lista de contribuições
- **Dialog de geração manual** de relatórios com mês/ano
- **Página WhatsApp** (`/whatsapp`) para escanear o QR Code pelo navegador, com status em tempo real e botão de reconexão
- **Google Sheets real no modo dev** — flag `DEV_USE_REAL_SHEETS=true` permite testar com a planilha real sem sair do modo dev
- **WhatsApp service local** — script de dev local inclui Terminal 2 para rodar o WhatsApp service com webhook apontando para `localhost:8000`

## Documentação

- [Arquitetura](docs/ARCHITECTURE.md)
- [Google Sheets](docs/GOOGLE_SHEETS_SETUP.md)
- [WhatsApp](docs/WHATSAPP_SETUP.md)
- [Operação (equipe financeira)](docs/OPERACAO.md)

## Estrutura do repositório

```
backend/             # API, domínio, OCR, IA, tasks, PDF
  scripts/           # create_admin.py, seed_dev_data.py, seed_sheets.py
  tests/             # pytest + fakeredis + testcontainers
whatsapp-service/    # Ponte WhatsApp → webhook (endpoints /whatsapp/status, /qr, /reconnect)
frontend/            # SPA administrativa (shadcn/ui)
  src/pages/         # Dashboard, Contribuições, Membros, WhatsApp, ...
  src/components/ui/ # Componentes base (Button, Card, Dialog, ...)
docs/                # Guias e diagramas
```

## Critérios de aceitação

Ver seção 21 da especificação (`CDB_Shalom_Prompt_v3.md`). O projeto implementa as fases 1–6, com testes automatizados e CI-ready.

## Licença

Uso interno — Comunhão de Bens Shalom.