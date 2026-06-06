# Configuração do Google Sheets

## 1. Criar projeto no Google Cloud

1. Acesse [Google Cloud Console](https://console.cloud.google.com/).
2. Crie um projeto (ex.: `cdb-shalom`).
3. Ative a **Google Sheets API**.

## 2. Service Account

1. IAM → Service Accounts → Criar conta.
2. Baixe a chave JSON.
3. Salve como `secrets/google_sa.json` (não commitar).
4. No `.env`, defina `GOOGLE_SERVICE_ACCOUNT_JSON=/run/secrets/google_sa.json`.

## 3. Planilha

1. Crie uma planilha no Google Sheets.
2. Compartilhe com o e-mail da service account (Editor).
3. Copie o ID da URL para `GOOGLE_SPREADSHEET_ID`.

## 4. Abas obrigatórias

Execute após subir o backend:

```bash
docker compose exec backend python /app/scripts/seed_sheets.py
```

### 4.1 Aba canônica: **Doações** (Fase 5+)

A aba **Doações** é a **visão operacional oficial** para novos
lançamentos. Sincroniza **CONFIRMADO** e **PENDENTE**. A aba
``Registros`` é mantida apenas para retrocompatibilidade (não recebe
mais dados novos).

| Coluna | Origem |
|---|---|
| Protocolo | ``contrib.protocolo`` |
| Data | ``contrib.data_pagamento`` |
| Hora | ``contrib.hora_pagamento`` |
| Nome | ``membro.nome`` |
| Categoria | ``membro.categoria`` |
| Valor | ``contrib.valor`` |
| **Favorecido** | ``dados.favorecido`` (V2) |
| **Tipo Documento** | ``PIX``/``TED``/``DOC``/``BOLETO``/``OUTRO`` |
| Telefone | ``contrib.telefone`` |
| **Status** | ``confirmado`` / ``pendente`` |
| Confiança | ``contrib.confianca`` (0–100%) |
| **OCR Bruto** | preview (100 chars) para auditoria |

### 4.2 Abas legadas (retrocompatibilidade)

| Aba | Status |
|---|---|
| Membros | Ativa (fonte de cadastro) |
| **Registros** | **Legada** — não recebe mais dados novos |
| Pendências | Ativa (criada automaticamente) |
| Auditoria | Ativa (eventos do sistema + JSON da IA no campo Detalhes) |
| Dashboard | Ativa (fórmulas operacionais) |
| Configuração | Ativa (chave/valor — inclui ``MENSAGEM_PENDENCIA``) |
| Relatórios | Ativa (PDFs mensais) |

### 4.3 Colunas de todas as abas

| Aba | Colunas |
|-----|---------|
| Membros | Telefone, Nome, Categoria, Ativo |
| **Doações** | (acima) |
| Registros (legado) | Protocolo, Data, Hora, Nome, Categoria, Valor, Banco, Telefone, Status, Confiança (%) |
| Pendências | ID, Data, Telefone, Nome, Motivo, Status, Observação |
| Auditoria | Timestamp, Evento, Contribuição ID, Telefone, Detalhes |
| Dashboard | (fórmulas — ver spec seção 8) |
| Configuração | Chave, Valor, Descrição |
| Relatórios | Mês, Ano, Data Geração, Caminho Arquivo, Status |

## 5. Categorias válidas

`comunidade_de_vida`, `comunidade_de_alianca`, `obra`, `benfeitor`

## 6. Cache

- Membros: TTL padrão 5 min (`CACHE_MEMBROS_TTL_MIN` na aba Configuração).
- Invalidar: `POST /api/v1/admin/cache/flush` (perfil ADMINISTRADOR).
