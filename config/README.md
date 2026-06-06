# Configurações

Arquivos de configuração do CDB Shalom.

## Variáveis de Ambiente

O arquivo `.env.example` contém todas as variáveis de ambiente necessárias.  
Copie para `.env` na raiz do projeto e ajuste os valores:

```bash
cp config/.env.example .env
```

## Variáveis Principais

| Variável | Descrição | Default (dev) |
|---|---|---|
| `DATABASE_URL` | URL de conexão com o banco | `sqlite+aiosqlite:///...` |
| `REDIS_URL` | URL do Redis | `redis://localhost:6379/0` |
| `JWT_SECRET_KEY` | Chave secreta JWT | (alterar em produção) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Caminho para service account Google | `scripts/google_sa.json` |
| `GOOGLE_SPREADSHEET_ID` | ID da planilha Google Sheets | — |
| `WHATSAPP_SERVICE_URL` | URL do WhatsApp Service | `http://localhost:3000` |
| `CORS_ORIGINS` | Origens permitidas (CORS) | `http://localhost:5173` |
| `OLLAMA_BASE_URL` | URL do servidor Ollama | `http://localhost:11434` |
| `DEV_MODE` | Modo desenvolvimento | `true` |

Consulte `backend/src/config.py` para a lista completa de variáveis.