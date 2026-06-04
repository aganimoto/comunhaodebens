# CDB Shalom — Arquitetura

Sistema local de automação financeira para contribuições PIX via WhatsApp.

## Regra inviolável

A identidade do contribuinte é determinada **exclusivamente** pelo número de WhatsApp, consultado na aba **Membros** do Google Sheets (com cache Redis). A IA nunca identifica pessoas.

## Diagrama de componentes

```mermaid
flowchart TB
    subgraph clients [Operação]
        WA[WhatsApp Contribuinte]
        GS[Google Sheets]
        ADM[Frontend Admin]
    end

    subgraph docker [Docker Compose]
        WSS[whatsapp-service Node]
        BE[backend FastAPI]
        CW[celery-worker]
        CB[celery-beat]
        PG[(PostgreSQL)]
        RD[(Redis)]
        OL[Ollama]
        FE[frontend Vite]
    end

    WA --> WSS
    WSS -->|POST webhook HMAC| BE
    BE --> RD
    BE --> PG
    BE --> GS
    BE --> OL
    BE --> CW
    CW --> OL
    CW --> GS
    CW --> PG
    ADM --> FE
    FE --> BE
    CB --> CW
```

## Happy path

```mermaid
sequenceDiagram
    participant C as Contribuinte
    participant W as whatsapp-service
    participant B as backend
    participant S as Sheets Membros
    participant Q as Celery
    participant O as OCR/IA

    C->>W: imagem comprovante
    W->>B: POST webhook
    B->>S: lookup telefone cache 5min
    alt não cadastrado
        B->>C: MSG_NAO_CADASTRADO
        Note over B: sem OCR
    else cadastrado
        B->>Q: ocr + ia
        Q->>O: PaddleOCR + Ollama
        Q->>B: dados validados
        B->>B: protocolo + persist
        Q->>S: Registros + Dashboard
        B->>C: MSG_AGRADECIMENTO
    end
```

## Caminhos de erro

```mermaid
flowchart TD
    A[Comprovante recebido] --> B{Telefone em Membros?}
    B -->|não| P1[Pendência TELEFONE_NAO_CADASTRADO]
    P1 --> M1[MSG_NAO_CADASTRADO]
    B -->|sim| C[OCR + IA]
    C --> D{Parse OK?}
    D -->|não| P2[erro_processamento]
    D -->|sim| E{Duplicata?}
    E -->|sim| P3[comprovante_duplicado]
    E -->|não| F{confiança >= 0.80?}
    F -->|não| P4[ia_baixa_confianca revisão]
    F -->|sim| G[confirmado + protocolo]
```

## Camadas (Clean Architecture)

| Camada | Responsabilidade |
|--------|------------------|
| `domain` | Entidades, value objects, eventos, interfaces de repositório |
| `application` | Casos de uso, serviços de domínio, handlers de eventos |
| `infrastructure` | PostgreSQL, Redis, Sheets, OCR, Ollama, arquivos |
| `api` | FastAPI, middleware, DI |
| `tasks` | Celery (OCR, IA, Sheets, PDF, backup) |

## ADRs resumidas

1. **Identidade por telefone** — Sheets é fonte da verdade para membros; IA só extrai valor/data/banco.
2. **HTTP entre WhatsApp e backend** — Contrato simples vs WebSocket.
3. **SPA Vite** — Admin não precisa SSR; HMR rápido em dev.
4. **Protocolo via tabela `sequencias`** — `SELECT FOR UPDATE` evita race sem arquivo em disco.
5. **Logs com hash de telefone** — LGPD: `SHA256(telefone)[:8]` apenas.

## Comunicação entre serviços

| De | Para | Protocolo |
|----|------|-----------|
| whatsapp-service | backend | `POST /api/v1/webhooks/whatsapp` + HMAC |
| backend | whatsapp-service | `POST /send` (mensagens) |
| backend | Ollama | HTTP REST |
| celery | PostgreSQL, Redis, Sheets | async/sync conforme módulo |
