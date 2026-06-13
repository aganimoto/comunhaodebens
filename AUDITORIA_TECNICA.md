# Auditoria Técnica Completa — CDB Shalom

**Data:** 12/06/2026  
**Escopo:** Backend (FastAPI/Python), Frontend (React/TypeScript), Infraestrutura  
**Commit analisado:** `e23c439d6a7ce7cad3014fc804ea09853958fbb6`

---

## 1. MAPEAMENTO GERAL

### Estrutura do Projeto

```
comunhaodebens/
├── backend/           # FastAPI + Celery + SQLAlchemy + Google Sheets
│   ├── src/
│   │   ├── api/           # Rotas REST + middleware auth + SSE
│   │   ├── application/   # Use cases, services (classificador, identificação, notificação)
│   │   ├── domain/        # Entidades (Contribuicao, Membro, Pendencia), Value Objects, Repositories (interfaces)
│   │   ├── infrastructure/# Database (SQLAlchemy), Cache (Redis), Sheets, OCR, AI (Ollama)
│   │   └── tasks/         # Celery tasks (OCR, backup, relatório, sheets)
│   └── tests/         # Testes com pytest
├── frontend/          # React + Vite + TypeScript + Tailwind
│   └── src/
│       ├── pages/     # Dashboard, Login, Contribuições, Pendências, Membros, Relatorios, WhatsApp
│       ├── components/# UI components (shadcn-like) + OCRProgressBar
│       ├── stores/    # Zustand (auth)
│       ├── lib/       # Axios API client
│       └── hooks/     # Toast custom hook
├── whatsapp-service/  # Serviço externo de WhatsApp
├── test_ocr/          # Scripts de teste de OCR
├── infra/docker/      # Docker Compose
├── scripts/           # Scripts auxiliares
└── shared/media/      # Mídias compartilhadas
```

### Stack Tecnológica

| Camada       | Tecnologia                                          | Versão      |
|-------------|-----------------------------------------------------|-------------|
| Backend     | Python 3.12+                                        | >=3.12      |
| API         | FastAPI                                             | >=0.111     |
| ORM         | SQLAlchemy 2.0 (assíncrono)                         | (implícito) |
| DB          | PostgreSQL (produção) / SQLite (dev/testes)         | -           |
| Cache/Queue | Redis + Celery                                      | >=5.0/5.4   |
| Storage     | Google Sheets (primário) + Google Drive (mídias)    | -           |
| OCR         | EasyOCR (padrão) / PaddleOCR / Tesseract            | -           |
| AI          | Ollama (Llama 3.2 1B) via HTTP                      | -           |
| PDF         | WeasyPrint                                          | >=62        |
| Auth        | JWT (python-jose) + bcrypt                          | -           |
| Frontend    | React 18 + TypeScript 5.5                           | -           |
| Build       | Vite 5                                               | -           |
| State       | Zustand + TanStack Query                            | -           |
| UI          | Tailwind CSS + shadcn/ui (Radix) + Recharts         | -           |
| Testes      | pytest + vitest                                     | -           |

### Fluxo Principal da Aplicação

1. **Usuário envia comprovante PIX via WhatsApp** → WhatsApp Service → Webhook (HMAC)
2. **Webhook** → `ProcessarComprovanteUseCase` → valida telefone → identifica membro (Sheets + Redis)
3. **OCR Task** (Celery ou asyncio) → EasyOCR → Classificador (palavras-chave) → Ollama (opcional) → Regex (valor/data)
4. **Resultado** → Grava em Google Sheets (Doações) + Auditoria + Notificação WhatsApp
5. **Frontend** → Dashboard (stats) → Consulta dados do Google Sheets via API

---

## 2. ERROS ATUAIS (BUGS)

### 🔴 CRÍTICO

#### [BUG-01] `connection.py` referencia `settings.database_url` inexistente
**Arquivo:** `backend/src/infrastructure/database/connection.py:8`  
**Problema:** `settings.database_url` não está definido em `Settings` (config.py). A classe `Settings` não possui o campo `database_url`.  
**Impacto:** Crash total ao iniciar qualquer operação que dependa de banco SQL (backup, repositories).  
**Correção:** Adicionar `database_url: str = "sqlite+aiosqlite:///dev.db"` em `Settings` ou remover referência.

#### [BUG-02] Auth: hash de senha gerado a cada login, sem persistência
**Arquivo:** `backend/src/api/routes/auth.py:44-53`  
**Problema:** A rota `/login` gera `_hash_senha(settings.bootstrap_admin_password)` a cada requisição. Como bcrypt usa salt aleatório, o hash **nunca** corresponde ao hash armazenado (que não existe, pois não há banco de admin). O login só funciona se a senha for a mesma do `bootstrap_admin_password`, e apenas compara com o hash gerado no momento.  
**Efeito prático:** Se a senha no `.env` for alterada **após** criar o admin no banco (modelo `UsuarioAdminModel`), o login via JWT do banco SQL nunca funcionará. O endpoint de login ignora o banco SQL.  
**Correção:** Ou usar senha única do settings SEM hash (comparação direta, já que só existe 1 admin), ou integrar com `UsuarioAdminModel` real.

#### [BUG-03] Frontend `Dashboard.tsx` requer campos que o backend não retorna
**Arquivo:** `frontend/src/pages/Dashboard.tsx:82` + tipo `Stats` (linhas 54-67)  
**Problema:** O tipo `Stats` espera `contribuicoes_revisao`, `contribuicoes_processando`, `pendencias_ocr`, `processando_hashes`. O backend (`admin.py:127-136`) retorna `DashboardStats` que **não** tem esses campos. O backend retorna `ultimas_contribuicoes` com campos diferentes dos esperados.  
**Resultado:** Dashboard exibe "—" para campos ausentes, gráfico de distribuição quebra, seção de pendências OCR fica vazia.  
**Correção:** Alinhar contrato frontend/backend ou adicionar campos faltantes no backend.

#### [BUG-04] Reprocessar no Dashboard usa `c.id` mas `ContribuicaoResumo` não tem `id`
**Arquivo:** `frontend/src/pages/Dashboard.tsx:281`  
**Problema:** `reprocessar.mutate(c.id)` referencia `c.id` no tipo `ContribuicaoResumo` (linha 36), que só tem `protocolo`, `telefone`, `valor`, `data_pagamento`, `status`, `confianca` — sem `id`. Backend espera protocolo via URL path.  
**Impacto:** Erro de tipagem TS e runtime indefinido.  
**Correção:** Mudar para `reprocessar.mutate(c.protocolo)` e ajustar endpoint ou adicionar `id` ao tipo.

### 🟡 ALTO

#### [BUG-05] `vite.config.ts` e `vite.config.mjs` duplicados
**Arquivos:** `frontend/vite.config.ts` (linha 1-21) e `frontend/vite.config.mjs` (linha 1-24)  
**Problema:** Ambos fazem exatamente a mesma configuração. `package.json` usa `vite.config.mjs`. O `.ts` é redundante e pode causar confusão.  
**Correção:** Remover `vite.config.ts` e manter apenas `.mjs`.

#### [BUG-06] Sheets: range fixo `A1:J1000` ignora dados além da linha 1000
**Arquivos:** 
- `backend/src/api/routes/contribuicoes.py:38` — `Doações!A1:J1000`
- `backend/src/api/routes/admin.py:46` — `Doações!A1:J5000`
- `backend/src/api/routes/admin.py:53` — `Pendências!A1:G5000`
- `backend/src/api/routes/pendencias.py:22` — `Pendências!A1:G5000`
**Problema:** Ranges fixos limitam a quantidade de dados. Com crescimento, dados além do range são invisíveis.  
**Correção:** Usar range sem limite inferior (ex: `Doações!A:J`) ou paginar via API Sheets.

#### [BUG-07] `sheets_writer.py` — `append_auditoria` parâmetro `detalhes_dict` nomeado incorretamente
**Arquivo:** `backend/src/infrastructure/sheets/sheets_writer.py:126-158`  
**Problema:** O método aceita `detalhes_dict` mas na task `ocr_task.py:202` chama com argumento nomeado `detalhes_dict=`, porém em outros lugares (webhooks.py, processar_comprovante.py) chama sem o dict. Inconsistência na assinatura entre chamadas.  
**Correção:** Padronizar assinatura.

#### [BUG-08] `backup_task.py` — dependência de `settings.database_url` que não existe
**Arquivo:** `backend/src/tasks/backup_task.py:111`  
**Problema:** `settings.database_url` não existe em `Settings`. Backup task quebra ao verificar se é PostgreSQL.  
**Correção:** Adicionar `database_url` em `Settings` ou usar `DATABASE_URL` de env var diretamente.

#### [BUG-09] `member_categoria` tratado como Enum mas sheets_writer recebe string
**Arquivo:** `backend/src/domain/entities/membro.py:7-11`  
**Problema:** `CategoriaMembro` é Enum, mas `identificacao_service.py` retorna `MembroSheets` com `categoria: str`. Em `processar_comprovante.py:62`, `membro.categoria` (string) é passado como `membro_categoria` para `ocr_task.py`. Sem validação.  
**Correção:** Validar categoria contra Enum antes de usar.

---

## 3. RISCOS FUTUROS

### 🔴 CRÍTICO

#### [RISCO-01] Dupla fonte de verdade: SQL + Google Sheets
**Arquivos:** Múltiplos — `infrastructure/database/` (SQL) vs `infrastructure/sheets/` (Sheets)  
**Problema:** O projeto tem modelos SQLAlchemy completos (`ContribuicaoModel`, `MembroModel`, etc.), repositórios SQL (`ContribuicaoRepository`), mas o fluxo real escreve **apenas** no Google Sheets. Os repositórios SQL são instanciáveis mas nunca usados no fluxo principal. Isso cria:
- Dupla manutenção
- Inconsistência potencial se ambos forem usados
- Código morto significativo  
**Impacto:** Confusão arquitetural, bugs de sincronia, dificuldade de onboarding.

#### [RISCO-02] JWT Secret hardcoded com valor de desenvolvimento
**Arquivo:** `backend/src/config.py:38`  
**Problema:** `jwt_secret_key` padrão é `"dev-jwt-secret-change-me-64-chars-minimum-for-hs256"`. Se não for alterado em produção, qualquer um pode forjar JWTs.  
**Correção:** Garantir que em produção o `.env` tenha chave forte. Adicionar validação em `get_settings()` que emita warning se for o valor padrão.

#### [RISCO-03] Webhook secret também hardcoded
**Arquivo:** `backend/src/config.py:36`  
**Problema:** `whatsapp_webhook_secret` padrão é `"dev-secret-change-me"`. Mesmo risco do JWT.  
**Correção:** Mesma recomendação.

#### [RISCO-04] Nenhum rate limiting na API
**Arquivos:** Todos os endpoints  
**Problema:** Não há proteção contra brute force em `/auth/login` nem contra abuso em webhooks.  
**Correção:** Adicionar `slowapi` ou middleware de rate limiting.

#### [RISCO-05] Google Sheets como banco de dados primário
**Arquivo:** `backend/src/infrastructure/sheets/`  
**Problema:** Sheets não é transacional, não suporta concorrência, tem limite de 10M células, e latência alta. Para um sistema financeiro, pode causar:
- Duplicatas em race conditions
- Timeout em pico de uso
- Perda de dados em escrita concorrente  
**Correção:** Migrar para banco SQL de verdade (PostgreSQL) como fonte primária, usando Sheets apenas como exportação/visualização.

### 🟡 ALTO

#### [RISCO-06] Docker: ambos backend e frontend EXPOSE na porta 8000
**Verificar Dockerfiles**  
**Problema:** Possível conflito se ambos expuserem mesma porta.

#### [RISCO-07] `fakeredis` em produção `dev_mode`
**Arquivo:** `backend/src/infrastructure/cache/redis_client.py:16-18`  
**Problema:** `dev_mode` usa `fakeredis` que é incompatível com Redis集群 e não persiste dados. Se `dev_mode=True` acidentalmente em produção, cache não funciona e tarefas Celery (que dependem de Redis real) quebram silenciosamente.  
**Correção:** Adicionar verificação para impedir `dev_mode` em produção.

#### [RISCO-08] EasyOCR sem GPU + timeout: até 120s por imagem
**Arquivo:** `backend/src/infrastructure/ocr/easyocr_service.py:58-62`  
**Problema:** EasyOCR com `gpu=False` pode levar de 30s a 120s por imagem. Sem timeout no worker Celery, pode travar tarefas.  
**Correção:** Configurar `soft_time_limit` e `time_limit` nas tasks Celery.

#### [RISCO-09] `_extrair_valor` duplicado em 3 arquivos diferentes
**Arquivos:**
- `backend/src/application/services/classificador_comprovante.py:39-57`
- `backend/src/infrastructure/ocr/easyocr_service.py:116-134`
- `backend/src/infrastructure/ai/ollama_service.py:40-59`  
**Problema:** Lógica de extração de valor duplicada 3x, cada uma com implementação ligeiramente diferente. Pode gerar resultados inconsistentes.  
**Correção:** Extrair para um utility compartilhado.

#### [RISCO-10] Tratamento de erro no webhook: sem retry
**Arquivo:** `backend/src/api/routes/webhooks.py:71-77`  
**Problema:** Se `ProcessarComprovanteUseCase.executar()` lançar exceção (ex: Redis down), o webhook retorna erro 500 sem retry. O comprovante é perdido.  
**Correção:** Adicionar fila de dead letter ou task de retry.

---

## 4. CÓDIGO INÚTIL / DÍVIDA TÉCNICA

### Código Morto

#### [MORTO-01] Repositórios SQL — `ContribuicaoRepository` nunca usado no fluxo real
**Arquivo:** `backend/src/infrastructure/database/repositories/contribuicao_repository.py` (97 linhas)  
**Prova:** Nenhum use case ou service importa `ContribuicaoRepository`. O fluxo real usa `SheetsWriter` e `SheetsClient`.  
**Impacto:** ~100 linhas de código não testado e não usado.

#### [MORTO-02] `IContribuicaoRepository` e `IMembroRepository` — interfaces não implementadas
**Arquivos:**
- `backend/src/domain/repositories/icontribuicao_repository.py`
- `backend/src/domain/repositories/imembro_repository.py`  
**Problema:** `IContribuicaoRepository` tem implementação (`ContribuicaoRepository`), mas `IMembroRepository` não tem implementação concreta.  
**Impacto:** Código morto + dívida técnica.

#### [MORTO-03] `Membro` domain entity vs `MembroSheets` — duplicação
**Arquivos:**
- `backend/src/domain/entities/membro.py` — entidade de domínio
- `backend/src/infrastructure/sheets/membros_reader.py:12-16` — `MembroSheets` dataclass  
**Problema:** Duas representações de membro com campos quase idênticos. `to_membro_entity` em `membros_reader.py:48` tenta converter, mas não é chamado em lugar nenhum fora de teste.  
**Impacto:** Confusão de responsabilidades.

#### [MORTO-04] `MembrosReader.to_membro_entity()` — nunca chamado
**Arquivo:** `backend/src/infrastructure/sheets/membros_reader.py:48-55`  
**Prova:** `IdentificacaoService.identificar()` retorna `MembroSheets`, não `Membro`.  
**Correção:** Remover ou usar de fato.

#### [MORTO-05] `vite.config.ts` — duplicata de `vite.config.mjs`
**Arquivo:** `frontend/vite.config.ts` (20 linhas)  
**Prova:** `package.json` usa `vite.config.mjs`.  
**Correção:** Remover.

#### [MORTO-06] `backend/src/application/reports/relatorio_service.py` — serviço de relatório não usado?
**Verificar.** Se implementa geração de PDF via WeasyPrint, mas rota usa Celery task.

#### [MORTO-07] `backend/src/api/routes/__init__.py` — vazio
**Arquivo:** `backend/src/api/routes/__init__.py`  
**Problema:** Arquivo vazio, sem imports.  
**Correção:** Remover ou preencher.

### Código Duplicado

#### [DUP-01] `_extrair_valor` em 3 lugares
Listado em RISCO-09. Função idêntica em:
- `classificador_comprovante.py:39`
- `easyocr_service.py:116`
- `ollama_service.py:40`

#### [DUP-02] `_KEYWORDS_COMPROVANTE` duplicado
**Arquivos:**
- `backend/src/application/services/classificador_comprovante.py:18-24`
- `backend/src/infrastructure/ocr/easyocr_service.py:30-36`  
**Problema:** Mesmo conjunto de palavras-chave definido duas vezes.

#### [DUP-03] Lógica de formatação SSE duplicada
**Arquivos:**
- `backend/src/api/routes/debug.py:29-31`
- `backend/src/api/routes/ocr_progress.py:27-29`  
**Problema:** `_sse_payload` idêntica em ambos.  
**Correção:** Extrair para utilitário compartilhado.

---

## 5. OPORTUNIDADES DE MELHORIA

### Arquitetura e Padrões

#### [MELHORIA-01] Definir fonte de dados única
**Recomendação:** Abandonar SQLAlchemy + Google Sheets como dupla. Escolher:
- **Opção A** (recomendada): PostgreSQL como fonte primária, Google Sheets como exportação
- **Opção B**: Google Sheets como fonte primária, remover SQLAlchemy  
**Impacto:** Reduz complexidade em ~40%, elimina código morto, simplifica manutenção.

#### [MELHORIA-02] Adicionar injeção de dependência explícita
**Problema:** Serviços são instanciados diretamente (ex: `SheetsWriter()`) sem DI. Dificulta testes e substituição de implementações.  
**Recomendação:** Usar FastAPI `Depends()` ou container DI.  
**Arquivos afetados:** Todos os use cases e services.

#### [MELHORIA-03] Centralizar lógica de extração de valor/data do OCR
**Recomendação:** Criar `src/application/services/extracao_service.py` com as funções de regex atualmente duplicadas.  
**Impacto:** Elimina duplicação, garante consistência.

#### [MELHORIA-04] Implementar refresh token
**Arquivo:** `backend/src/api/routes/auth.py:65-67`  
**Problema:** Rota `/refresh` retorna 501. JWT sem refresh obriga re-login a cada 8h.  
**Correção:** Implementar refresh token com Redis.

### Performance

#### [MELHORIA-05] Adicionar cache nas consultas de Sheets
**Arquivos:** `contribuicoes.py`, `admin.py`, `pendencias.py`  
**Problema:** Toda requisição ao dashboard faz 2-3 chamadas ao Google Sheets (latência ~500ms cada).  
**Recomendação:** Cachear resultados em Redis com TTL curto (30s).

#### [MELHORIA-06] Range dinâmico no Sheets
**Arquivos:** `contribuicoes.py`, `admin.py`, `pendencias.py`  
**Recomendação:** Usar `sheet_name!A:Z` em vez de `A1:J5000` para evitar limites artificiais.

#### [MELHORIA-07] Timeout no EasyOCR com fallback
**Arquivo:** `backend/src/infrastructure/ocr/easyocr_service.py`  
**Recomendação:** Adicionar timeout de 60s no processamento. Se exceder, fallback para Tesseract.

### Segurança

#### [MELHORIA-08] Validar entrada de `nome_sugerido` no webhook
**Arquivo:** `backend/src/api/routes/webhooks.py:28`  
**Problema:** `nome_sugerido` é aceito direto do webhook sem validação. Risco de XSS se for exibido no frontend.  
**Correção:** Sanitizar ou limitar caracteres.

#### [MELHORIA-09] Logs sem dados sensíveis
**Arquivos:** `ocr_task.py`, `processar_comprovante.py`  
**Problema:** Alguns logs incluem telefone parcial. OK para LGPD, mas verificar se `_hash_telefone_log` é usado consistentemente.  
**Correção:** Garantir que **nenhum** log tenha telefone completo.

### Manutenibilidade

#### [MELHORIA-10] Adicionar `__init__.py` com exports
**Arquivos:** Todas as camadas  
**Recomendação:** Exportar classes públicas nos `__init__.py` para simplificar imports.

#### [MELHORIA-11] Type hints completos
**Problema:** Muitas funções sem type hints nos parâmetros.
- `backend/src/infrastructure/ocr/easyocr_service.py:229` — `results` sem tipo
- `backend/src/infrastructure/ocr/easyocr_service.py:230` — `item` sem tipo  
**Correção:** Adicionar `Any` ou tipos concretos.

#### [MELHORIA-12] Testes para o fluxo principal
**Problema:** Não há testes que cubram o pipeline completo: webhook → use case → OCR → sheets. Testes existentes são unitários ou de API isolados.  
**Recomendação:** Criar teste de integração end-to-end com fakeredis + mock sheets.

---

## 6. PLANO DE AÇÃO

### 🔴 Crítico (Resolver imediatamente)

| # | Problema | Arquivo | Linha | Correção | Impacto |
|---|----------|---------|-------|----------|---------|
| 1 | `settings.database_url` não existe | `connection.py` | 8 | Adicionar campo em `Settings` | Crash ao usar banco |
| 2 | Auth: hash sem persistência | `auth.py` | 51 | Comparar senha direta ou integrar com `UsuarioAdminModel` | Login quebrado |
| 3 | Dashboard Stats incompatível | `Dashboard.tsx` | 54-67 | Alinhar tipo `Stats` com backend | Dashboard quebrado |
| 4 | `c.id` inexistente em reprocessar | `Dashboard.tsx` | 281 | Usar `c.protocolo` | Erro runtime no reprocessar |
| 5 | Webhook sem retry | `webhooks.py` | 71 | Adicionar retry com Celery | Perda de comprovantes |
| 6 | Rate limiting ausente | Todas rotas | - | Adicionar `slowapi` | Risco de brute force |

### 🟡 Alto (Resolver na sprint atual)

| # | Problema | Arquivo | Linha | Correção | Impacto |
|---|----------|---------|-------|----------|---------|
| 7 | JWT secret hardcoded | `config.py` | 38 | Validar em produção | Risco de segurança |
| 8 | Webhook secret hardcoded | `config.py` | 36 | Validar em produção | Risco de segurança |
| 9 | Sheets range fixo (1000 linhas) | 4 arquivos | - | Usar range dinâmico | Dados invisíveis |
| 10 | Backup task quebra sem `database_url` | `backup_task.py` | 111 | Adicionar campo em Settings | Backup não funciona |
| 11 | Repositórios SQL não usados | `repositories/` | todo | Decidir: usar ou remover | Código morto |
| 12 | `vite.config.ts` duplicado | `/frontend/` | - | Remover | Confusão no build |
| 13 | EasyOCR sem timeout | `easyocr_service.py` | 58 | Adicionar timeout | Worker travado |

### 🟢 Médio (Próximas sprints)

| # | Problema | Arquivo | Linha | Correção | Impacto |
|---|----------|---------|-------|----------|---------|
| 14 | `_extrair_valor` triplicado | 3 arquivos | - | Centralizar em `extracao_service.py` | Manutenibilidade |
| 15 | SSE payload duplicado | 2 arquivos | - | Extrair utilitário | Manutenibilidade |
| 16 | `_KEYWORDS_COMPROVANTE` duplicado | 2 arquivos | - | Centralizar em constantes | Manutenibilidade |
| 17 | Refresh token não implementado | `auth.py` | 65 | Implementar com Redis | UX |
| 18 | Sem cache nas consultas Sheets | routes/ | - | Cache em Redis (30s TTL) | Performance |
| 19 | `MembroSheets` vs `Membro` | 2 arquivos | - | Unificar representação | Dívida técnica |
| 20 | Faltam type hints | `easyocr_service.py` | 229-230 | Adicionar tipos | Manutenibilidade |

### 🔵 Baixo (Backlog técnico)

| # | Problema | Arquivo | Linha | Correção | Impacto |
|---|----------|---------|-------|----------|---------|
| 21 | `fakeredis` em dev_mode | `redis_client.py` | 16 | Validar ambiente | Risco baixo |
| 22 | `__init__.py` vazios | vários | - | Adicionar exports | Organização |
| 23 | Migrar para injeção de dependência | vários | - | Adicionar DI | Arquitetura |
| 24 | Testes E2E do pipeline | tests/ | - | Criar teste de integração | Qualidade |

---

## RESUMO

| Categoria | Qtde | Descrição |
|-----------|------|-----------|
| **Bugs críticos** | 4 | Login quebrado, Dashboard inconsistente, `database_url` ausente, crash em reprocessar |
| **Bugs altos** | 5 | Sheets limitado, `vite.config` duplicado, backup quebrado |
| **Riscos críticos** | 5 | Dupla fonte de verdade, secrets hardcoded, sem rate limit, Sheets como DB, sem retry webhook |
| **Riscos altos** | 4 | `fakeredis` em prod, OCR sem timeout, código duplicado, perda de comprovantes |
| **Código morto** | 7 | Repositórios SQL não usados, interfaces sem implementação, entidades duplicadas, config duplicada |
| **Código duplicado** | 3 | Extração de valor (3x), keywords (2x), SSE payload (2x) |
| **Melhorias** | 12 | Cache, DI, testes, segurança, performance, organização |

**Prioridade zero:** Corrigir bugs 1-4 (Críticos) e risco 5 (retry webhook) — todos impedem o funcionamento básico do sistema.