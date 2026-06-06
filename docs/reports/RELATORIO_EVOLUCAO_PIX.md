# Relatório de Análise — Evolução do Processamento de Comprovantes PIX

**Data:** 2026-06-05
**Escopo:** Avaliação da base atual e plano de evolução para processamento
automático de comprovantes PIX via WhatsApp com Tesseract + Ollama (Qwen3:4b).

> **Observação importante:** boa parte do fluxo descrito no briefing **já
> está implementado** no projeto. Este relatório identifica o que existe,
> o que precisa ser ajustado e o que precisa ser criado do zero.

---

## 1. Arquitetura Atual

### 1.1 Estrutura de pastas

```
comunhaodebens/
├── backend/                  FastAPI + SQLAlchemy 2.0 async (Python 3.12)
│   ├── alembic/              Migrações (1 migration: 001_initial_schema)
│   ├── src/
│   │   ├── api/              Rotas FastAPI + middleware JWT
│   │   ├── application/      Use cases + services de domínio
│   │   ├── domain/           Entidades, value objects, eventos, repos
│   │   ├── infrastructure/   DB, cache, AI, OCR, Sheets
│   │   └── tasks/            Celery (ocr, sheets, backup, relatorio)
│   └── scripts/              bootstrap_local_db, create_admin, seed_dev_data
│
├── whatsapp-service/         Node.js + Express + whatsapp-web.js
│   └── src/
│       ├── handlers/         message_handler, media_handler
│       └── api/              backend_client (HMAC webhook)
│
├── frontend/                 Vite + React + TypeScript + TanStack Query
│   └── src/
│       ├── pages/            Dashboard, Contribuicoes, Pendencias, Membros,
│       │                     Relatorios, WhatsAppConnect, Login
│       ├── components/       layout/, ui/ (Card, Button, Badge, Table, ...)
│       ├── hooks/            use-toast
│       ├── lib/              api (axios + interceptor JWT)
│       └── stores/           auth.store (Zustand)
│
├── infra/docker/             docker-compose + Modelfile Ollama
├── config/                   .env.example + README
├── shared/media/             Volume compartilhado para mídias
├── docs/                     ARCHITECTURE, GOOGLE_SHEETS_SETUP, OPERACAO,
│                             WHATSAPP_SETUP, reports/
└── scripts/                  dev/, windows/ (.bat helpers)
```

### 1.2 Fluxo do WhatsApp (já existente)

```
[Contribuinte]
    │  (imagem/PDF)
    ▼
[whatsapp-service :3000]
    │ 1. message_handler extrai telefone (10–13 dígitos, fallback para LID)
    │ 2. media_handler baixa mídia (retry x3 com backoff)
    │ 3. salva em /shared/media/{telefone}_{stamp}.{jpg|pdf}
    │ 4. calcula SHA-256
    │ 5. POST HMAC-SHA256
    ▼
[backend FastAPI :8000  POST /api/v1/webhooks/whatsapp]
    │ 1. _verify_hmac() valida assinatura
    │ 2. WhatsAppWebhookPayload → NovoComprovanteRecebido
    │ 3. ProcessarComprovanteUseCase.executar()
    │     ├─ valida Telefone (value object E.164)
    │     ├─ grava MensagemRecebidaModel
    │     ├─ IdentificacaoService.identificar(telefone)
    │     │     └─ MembrosReader.buscar_por_telefone (Sheets com cache Redis 5 min)
    │     ├─ se não cadastrado → pendência + msg_nao_cadastrado
    │     ├─ se hash_imagem duplicado → pendência + msg
    │     └─ delega para Celery (produção) ou asyncio (dev_mode):
    ▼
[tasks/ocr_task.py  processar_ocr_e_ia]
    │ 1. PaddleOCRService.processar()
    │     └─ preprocessor.py (OpenCV: grayscale, denoise, threshold, deskew)
    │ 2. OllamaService.extrair_de_imagem(imagem, texto_ocr)
    │     └─ qwen2.5-vl:7b / fallback qwen2.5:7b
    │ 3. response_parser.parse_dados_comprovante() → JSON validado
    │ 4. RegistrarContribuicaoUseCase.executar()
    │     ├─ ProtocoloService.gerar() (tabela sequencias, SELECT FOR UPDATE)
    │     ├─ ContribuicaoRepository.save()
    │     ├─ se CONFIRMADO → SheetsWriter.append_registro + msg_agradecimento
    │     └─ se REVISAO → msg_revisao + PendenciaModel(IA_BAIXA_CONFIANCA)
    ▼
[Sheets]  Membros | Registros | Pendências | Auditoria | Config | Dashboard
[WhatsApp]  resposta ao contribuinte
```

### 1.3 Serviços já existentes

| Serviço | Local | Observação |
|---|---|---|
| WhatsApp Service | `whatsapp-service/src/` | Já com HMAC, retry, QR, reconexão |
| OCR | `backend/src/infrastructure/ocr/paddle_ocr_service.py` | **PaddleOCR PT-BR** (não Tesseract) |
| Preprocessamento OCR | `infrastructure/ocr/preprocessor.py` | OpenCV headless |
| IA (Ollama) | `infrastructure/ai/ollama_service.py` | **qwen2.5-vl:7b** + fallback qwen2.5:7b |
| Parser IA | `infrastructure/ai/response_parser.py` | Extrai JSON mesmo com markdown |
| Sheets Writer | `infrastructure/sheets/sheets_writer.py` | append_registro/pendencia/auditoria |
| Sheets Reader | `infrastructure/sheets/membros_reader.py` + `config_reader.py` | Com cache Redis 5 min |
| Sheets Client | `infrastructure/sheets/sheets_client.py` | **Fallback local JSON** quando sem credenciais |
| Identificação | `application/services/identificacao_service.py` | **Exclusivamente por telefone** (regra da arquitetura) |
| Notificação | `application/services/notificacao_service.py` | Templates via Sheets `Configuração` |
| Protocolo | `application/services/protocolo_service.py` | Diário, atômico, sem arquivo |
| Cache | `infrastructure/cache/redis_client.py` | `fakeredis` em dev, Redis real em prod |
| Tarefas (Celery) | `tasks/{ocr,sheets,backup,relatorio}_task.py` | Beat agenda backup 02:00 e relatório dia 1º 06:00 |
| Health | `api/routes/health.py` | Checa postgres, redis, ollama, sheets, whatsapp |

### 1.4 Banco de dados atual (1 migration: `001_initial_schema`)

| Tabela | Colunas principais | Uso |
|---|---|---|
| `membros` | id, telefone (UNIQUE), nome, categoria, ativo, criado_em, atualizado_em | Cadastro (também lido do Sheets com cache) |
| `arquivos` | id, nome_original, caminho, hash_sha256, tamanho_bytes, mime_type | **Existe mas não é populada pelo fluxo atual** |
| `contribuicoes` | id, protocolo (UNIQUE), membro_id, telefone, valor, data_pagamento, hora_pagamento, banco, confianca, status, hash_imagem (UNIQUE), arquivo_id, criado_em, atualizado_em | Tabela central |
| `pendencias` | id, contribuicao_id, telefone, motivo, status, observacao, resolvido_por, resolvido_em, criado_em | Já com 6 motivos definidos |
| `auditoria` | id, timestamp, evento, contribuicao_id, telefone, detalhes (JSONB), nivel | Log estruturado |
| `mensagens_recebidas` | id, telefone, whatsapp_msg_id (UNIQUE), timestamp, tipo, texto, media_path, status | Mensagens cruas |
| `sequencias` | data (PK), ultimo_numero | Protocolo diário |
| `usuarios_admin` | id, email (UNIQUE), senha_hash, perfil, ativo, criado_em | Auth JWT |

### 1.5 Integrações e camadas de IA existentes

- **WhatsApp → Backend:** HTTP POST com `X-HMAC-Signature: sha256=...`
- **Backend → WhatsApp:** `POST {whatsapp_service_url}/send` (JSON `{telefone, mensagem}`)
- **Backend → Ollama:** `POST {ollama_base_url}/api/chat` (messages + image base64 opcional)
- **Backend → Sheets:** Google Sheets API v4 via service account; **fallback automático para `dev_data/sheets_fallback.json`** quando sem credenciais
- **IA atual:** `qwen2.5-vl:7b` (multimodal) com fallback `qwen2.5:7b` (texto)
- **OCR atual:** PaddleOCR PT-BR, preprocessamento com OpenCV
- **Cache:** Redis real em prod, `fakeredis` em dev (já configurado)
- **Auth:** JWT HS256, perfis `administrador | financeiro | consulta`
- **Middleware:** CORS, HTTP Bearer, log com structlog

### 1.6 Dependências atuais (pyproject.toml)

- **Web/API:** fastapi 0.111, uvicorn, pydantic 2.7, pydantic-settings
- **DB:** sqlalchemy[asyncio] 2.0, asyncpg, aiosqlite, alembic
- **Auth:** python-jose, passlib[bcrypt], bcrypt<5
- **Google:** google-api-python-client 2.130, google-auth 2.29
- **IA/OCR:** httpx, opencv-python-headless 4.9, numpy, **paddlepaddle + paddleocr** (opcional `[ocr]`)
- **Cache/Filas:** redis 5, celery 5.4, fakeredis
- **Outros:** structlog, weasyprint (PDF), apscheduler, python-multipart

> Tesseract **não está instalado nem declarado**. PaddleOCR está como dependência opcional.

### 1.7 Frontend (Vite + React + TS)

- Páginas: Login, Dashboard, Contribuicoes, Pendencias, Membros, Relatorios, WhatsAppConnect
- Componentes UI: `card.tsx`, `button.tsx`, `badge.tsx`, `table.tsx`, `input.tsx`, `select.tsx`, `utils.ts` (formatBRL, formatDate, formatDateTime, cn)
- Hooks: `use-toast`
- Axios com interceptor JWT (`lib/api.ts`)
- TanStack Query para fetching

---

## 2. Pontos de Integração com o Briefing

| Pedido do briefing | Status atual | O que muda |
|---|---|---|
| Receber imagem no WhatsApp | ✅ Existe (`media_handler.js` + `message_handler.js`) | Nada |
| OCR local | ✅ Existe, mas com **PaddleOCR** | Trocar/adicionar **Tesseract** (criar `tesseract_ocr_service.py` + flag no Settings) |
| Enviar texto para Ollama | ✅ Existe (`OllamaService.extrair_de_imagem/texto`) | Ajustar para **Qwen3:4b** |
| Extrair dados estruturados (JSON) | ✅ Existe, mas com schema `{valor,data,hora,banco,confianca}` | Migrar para `{valor,data_pix,favorecido,tipo_documento,confidence}` (parser retrocompatível) |
| Salvar em banco | ✅ Existe | **Adicionar colunas** `ocr_texto_bruto`, `ocr_dados_json`, `ocr_confianca_media` |
| Sincronizar Google Sheets | ✅ Existe (`SheetsWriter`) | Renomear aba `Registros` → `Doações`; sincronizar CONFIRMADO **e PENDENTE** |
| Enviar resposta personalizada | ✅ Existe (`NotificacaoService` + templates em `ConfigReader.DEFAULTS`) | Ajustar mensagens padrão (mas continuar configurável pelo Sheets) |
| Identificação por telefone (nunca IA) | ✅ Existe (regra da arquitetura) | Nada |
| Status PROCESSANDO / CONFIRMADO / PENDENTE / ERRO | ⚠️ Atualmente: `CONFIRMADO, REVISAO, DUPLICADO, ERRO` | Migrar `REVISAO` → `PENDENTE`; introduzir `PROCESSANDO` |
| Salvar imagem original | ⚠️ `MensagemRecebidaModel.media_path` salva, mas `arquivos` não é populada | Popular `ArquivoModel` e referenciar em `ContribuicaoModel.arquivo_id` (FK já existe) |
| Salvar texto OCR bruto e JSON IA | ❌ Não persistido | Adicionar colunas em `ContribuicaoModel` |
| Reprocessamento manual | ❌ Não existe | Novo endpoint `POST /contribuicoes/{id}/reprocessar` |
| Dashboard: total hoje/mês, últimas, pendências OCR, reprocessamento, consulta | ⚠️ Existe `/admin/dashboard/stats` simples | Expandir endpoint + nova página/bloco |
| `LIMIAR_CONFIANCA` (< 0.80 → PENDENTE) | ✅ Já existe no `ConfigReader` | Apenas renomear status final |

---

## 3. Arquivos que Precisam ser Alterados

### 3.1 Backend — novos arquivos

| Arquivo | Função |
|---|---|
| `src/infrastructure/ocr/tesseract_ocr_service.py` | Implementação Tesseract (com fallback PaddleOCR via flag) |
| `src/application/use_cases/reprocessar_comprovante.py` | Use case de reprocessamento |
| `src/api/routes/reprocessamento.py` | Endpoint `POST /contribuicoes/{id}/reprocessar` (ou dentro de `contribuicoes.py`) |
| `alembic/versions/002_evolucao_pix.py` | Migration: novos status, colunas OCR/JSON, ajuste default |
| `src/domain/entities/comprovante_processado.py` (opcional) | Encapsular `{imagem_path, ocr_texto, ocr_json, dados_estruturados}` |

### 3.2 Backend — arquivos a modificar (apenas pontos cirúrgicos)

| Arquivo | Mudança |
|---|---|
| `src/config.py` | Novos campos: `tesseract_cmd`, `tesseract_lang`, `ocr_engine` (tesseract\|paddle), `ollama_text_model=qwen3:4b` |
| `src/domain/entities/contribuicao.py` | Adicionar `StatusContribuicao.PROCESSANDO` e `.PENDENTE`; migrar `.REVISAO` → alias `.PENDENTE` (compat.) |
| `src/infrastructure/database/models.py` | `ContribuicaoModel`: + `ocr_texto_bruto TEXT`, `ocr_dados_json JSON`, `ocr_confianca_media NUMERIC(3,2)`; popular `ArquivoModel` |
| `src/infrastructure/ai/ollama_service.py` | Trocar `SYSTEM_PROMPT` para novo schema; `qwen3:4b` como text-only; manter compat. com multimodal |
| `src/infrastructure/ai/response_parser.py` | Novo `DadosComprovante`; parser retrocompatível (tenta novo, cai no antigo) |
| `src/tasks/ocr_task.py` | Persistir `ocr_texto_bruto`/`ocr_dados_json`/`ocr_confianca_media`; popular `ArquivoModel`; criar contribuição já com `PROCESSANDO` |
| `src/application/use_cases/processar_comprovante.py` | Criar `ContribuicaoModel` com `status=PROCESSANDO` (idempotente via `hash_imagem`) |
| `src/application/use_cases/registrar_contribuicao.py` | Aceitar novos campos (OCR bruto + JSON); usar `PENDENTE` em vez de `REVISAO` |
| `src/application/services/notificacao_service.py` | Adicionar `msg_pendencia(telefone, nome)` (template `MENSAGEM_PENDENCIA`) |
| `src/infrastructure/sheets/sheets_writer.py` | `append_registro` → `append_doacao` (alias); detalhes de auditoria com JSON IA |
| `src/infrastructure/sheets/config_reader.py` | Adicionar template `MENSAGEM_PENDENCIA` aos `DEFAULTS` |
| `src/infrastructure/sheets/seed.py` | Renomear aba `Registros` → `Doações` na inicialização |
| `src/api/routes/contribuicoes.py` | `POST /{id}/reprocessar`; `GET /{id}/comprovante` retorna imagem |
| `src/api/routes/admin.py` | Expandir `/admin/dashboard/stats` com `valor_hoje`, `valor_mes`, `ultimas_contribuicoes`, `pendencias_ocr` |
| `config/.env.example` | Novos toggles: `OCR_ENGINE=tesseract`, `TESSERACT_CMD=...`, `TESSERACT_LANG=por`, `OLLAMA_TEXT_MODEL=qwen3:4b` |

### 3.3 Frontend — arquivos a modificar

| Arquivo | Mudança |
|---|---|
| `src/lib/api.ts` | Já existe; nada a alterar (apenas consumir novos endpoints) |
| `src/pages/Dashboard.tsx` | Adicionar cards: total hoje, total mês, últimas 5 contribuições, pendências OCR com botão "Reprocessar" |
| `src/pages/Contribuicoes.tsx` | Adicionar coluna "Status" mais clara + botão "Ver comprovante" / "Reprocessar" |
| `src/pages/Pendencias.tsx` | Botão "Reprocessar" para pendências OCR/IA |
| `src/components/ui/badge.tsx` | (se já tiver