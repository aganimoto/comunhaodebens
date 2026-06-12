# Google Sheets — Configuração

O Google Sheets é o **único banco de dados** do sistema CDB Shalom.

---

## 1. Criar Service Account

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um novo projeto (ou selecione um existente)
3. Ative a API **Google Sheets API**
4. Crie uma **Service Account**:
   - Menu: IAM & Admin → Service Accounts
   - Clique em "Create Service Account"
   - Nome: `cdb-shalom` (ou similar)
   - Role: não precisa atribuir
5. Na service account criada, vá em "Keys" → "Add Key" → "Create new key"
   - Tipo: JSON
   - Baixe o arquivo

## 2. Configurar .env

```bash
# Caminho absoluto para o JSON da service account
GOOGLE_SERVICE_ACCOUNT_JSON=/caminho/para/service-account.json

# ID da planilha (trecho da URL)
GOOGLE_SPREADSHEET_ID=1wvY1TRVT4EskO50kB1r_8YEBfadqIKdtEMowdoyFFW0
```

> O `GOOGLE_SPREADSHEET_ID` está na URL da planilha:
> `https://docs.google.com/spreadsheets/d/1wvY1TRVT4EskO50kB1r_8YEBfadqIKdtEMowdoyFFW0/edit`
> O ID é `1wvY1TRVT4EskO50kB1r_8YEBfadqIKdtEMowdoyFFW0`.

## 3. Compartilhar a planilha

1. Abra a planilha no Google Sheets
2. Clique em "Compartilhar" (ícone de compartilhamento)
3. Adicione o e-mail da service account (formato: `nome@projeto.iam.gserviceaccount.com`)
4. Permissão: **Editor**

## 4. Estrutura das abas

### Aba `Membros` (obrigatória)
| Coluna | Descrição |
|--------|-----------|
| Telefone | Número com DDD (ex: `11999998888`) |
| Nome | Nome completo do membro |
| Categoria | Ex: `jovem`, `adulto`, `líder` |
| Ativo | `true` ou `false` |

### Aba `Doações` (dados do OCR)
| Coluna | Descrição |
|--------|-----------|
| Protocolo | ID único (ex: `20260612-A1B2C3`) |
| Data | Data ISO 8601 (ex: `2026-06-12`) |
| Nome | Nome do membro |
| Categoria | Categoria do membro |
| Valor | Valor em R$ (ex: `150.00`) |
| Favorecido | Nome do destinatário do PIX |
| Telefone | Telefone do membro |
| Status | `CONFIRMADO` ou `PENDENTE` |
| Confiança | Percentual (ex: `67%`) |
| OCR Preview | Preview do texto OCR (100 chars) |

### Aba `Registros` (legado, retrocompatível)
Mantida para compatibilidade com código antigo. Estrutura simplificada:
Protocolo, Data, Nome, Categoria, Valor, Telefone, Status, Confiança.

### Aba `Pendências`
| Coluna | Descrição |
|--------|-----------|
| ID | UUID da pendência |
| Data | Data ISO 8601 |
| Telefone | Telefone do membro |
| Nome | Nome do membro |
| Motivo | Tipo da pendência |
| Status | `aberto` |
| Observação | Detalhes adicionais |

### Aba `Auditoria`
| Coluna | Descrição |
|--------|-----------|
| Timestamp | Data/hora ISO 8601 |
| Evento | Tipo do evento (ex: `OCR_CONCLUIDO`) |
| Detalhes | Descrição detalhada |

### Aba `Configuração`
| Coluna | Descrição |
|--------|-----------|
| Chave | Nome da configuração |
| Valor | Valor da configuração |

Exemplo de configurações:
- `LIMIAR_CONFIANCA` = `0.80`
- `MENSAGEM_BEM_VINDO` = `Olá! Envie seu comprovante de contribuição.`

### Aba `Dashboard` (opcional)
| Coluna | Descrição |
|--------|-----------|
| Indicador | Nome do indicador |
| Valor | Valor do indicador |

## 5. Inicializar a planilha (seed)

```bash
cd backend
python -m src.infrastructure.sheets.seed
```

Este script:
- Cria as abas que não existem
- Adiciona cabeçalhos se as abas estiverem vazias
- Popula a aba Configuração com valores padrão

## 6. Backup

O Google Sheets tem histórico de versões nativo:
- Arquivo → Histórico de versões → Ver histórico de versões
- Pode restaurar qualquer versão anterior

Para backup externo:
```bash
# Exportar como Excel
pip install gspread
python scripts/backup_sheets.py
```

## 7. Permissões da API

A service account precisa das seguintes permissões:
- `https://www.googleapis.com/auth/spreadsheets` (leitura e escrita)

## 8. Problemas comuns

| Problema | Causa | Solução |
|----------|-------|---------|
| `403 Forbidden` | Planilha não compartilhada | Compartilhe com o e-mail da service account |
| `404 Not Found` | ID da planilha incorreto | Verifique o `GOOGLE_SPREADSHEET_ID` |
| `Quota exceeded` | Muitas requisições | Aguarde 1 minuto ou use cache Redis |
| `Service account not found` | JSON não configurado | Verifique o caminho em `GOOGLE_SERVICE_ACCOUNT_JSON` |