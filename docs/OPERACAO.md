# CDB Shalom — Operação

Guia de operação do sistema CDB Shalom.

---

## 1. Iniciar o sistema

### Desenvolvimento (Windows)

```cmd
scripts\windows\dev-all.bat
```

Ou manualmente em 3 terminais:

```cmd
# Terminal 1: Backend
cd backend
.venv\Scripts\activate
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: WhatsApp Service
cd whatsapp-service
npm start

# Terminal 3: Frontend
cd frontend
npm run dev
```

### Produção (Docker)

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build
```

---

## 2. Verificar status

### Backend
- Acesse http://localhost:8000/docs (Swagger)
- Verifique se a API responde

### Google Sheets
- Acesse a planilha no navegador
- Verifique se as abas existem: Membros, Doações, Registros, Pendências, Auditoria, Configuração

### Ollama (opcional)
```bash
ollama list
# Deve mostrar: llama3.2:1b
```

---

## 3. Fluxo de processamento

```
1. Membro envia foto de comprovante via WhatsApp
2. WhatsApp Service recebe e reencaminha para Backend
3. Backend identifica membro pelo telefone (Sheets + cache Redis)
4. Celery task dispara processamento OCR
5. EasyOCR extrai texto bruto da imagem
6. Classificador por palavras-chave valida se é comprovante
7. Regex extrai: valor (R$), data (dd/mm/aaaa), favorecido
8. Status determinado por confiança:
   - >= 0.80: CONFIRMADO
   - < 0.80: PENDENTE
9. Dados salvos na aba Doações do Google Sheets
10. Protocolo gerado (YYYYMMDD-HASH6)
11. WhatsApp notifica o contribuinte
```

---

## 4. Monitoramento

### Logs
- Logs do backend: terminal onde o uvicorn está rodando
- Logs do WhatsApp Service: terminal onde o node está rodando
- Logs do Celery: terminal onde o worker está rodando

### Google Sheets
- Aba **Auditoria**: eventos de processamento
- Aba **Pendências**: erros e pendências
- Aba **Doações**: todos os comprovantes processados

### Debug Logger
O sistema mantém um logger de debug em memória com hash do telefone (LGPD):
- `MODULO_OCR` — etapas do OCR
- `MODULO_IA` — etapas da IA/regex
- `MODULO_CLASSIFICADOR` — classificação por palavras-chave

---

## 5. Manutenção

### Limpar cache Redis
```bash
redis-cli FLUSHDB
```

### Resetar planilha
- Use o script `scripts/seed_sheets.py` para recriar cabeçalhos
- Ou recrie manualmente as abas no Google Sheets

### Atualizar modelo Ollama
```bash
ollama pull llama3.2:1b
```

### Backup
- Google Sheets: Arquivo → Histórico de versões
- Redis: `redis-cli BGSAVE`
- Arquivos de mídia: `shared/media/`

---

## 6. Solução de problemas

| Problema | Causa | Solução |
|----------|-------|---------|
| `ECONNREFUSED` no frontend | Backend não está rodando | Execute `run-backend.bat` ou `uvicorn` |
| Google Sheets não conecta | Service account não configurada | Configure `GOOGLE_SERVICE_ACCOUNT_JSON` e `GOOGLE_SPREADSHEET_ID` |
| `ModuleNotFoundError` | Dependências não instaladas | `pip install -e ".[dev]"` |
| OCR não funciona | EasyOCR não instalado | Execute `python -c "import easyocr; easyocr.Reader(['pt'])"` |
| `Porta já em uso` | Outro processo na mesma porta | Mude a porta ou mate o processo |
| Celery não conecta | Redis não está rodando | Inicie Redis ou ignore se não usar tarefas assíncronas |
| IA não responde | Ollama não está rodando | Inicie Ollama ou desabilite classificação |
| Dados não aparecem na planilha | Service account sem permissão | Compartilhe a planilha com a service account |

---

## 7. Segurança

### LGPD
- O sistema **NUNCA** armazena CPF, nome completo ou telefone em logs
- Logs usam hash: `SHA256(telefone)[:8]`
- A IA **NUNCA** recebe dados pessoais

### Autenticação
- JWT com expiração de 8 horas
- Perfis: `administrador`, `financeiro`, `consulta`
- Senha padrão: `TroqueEstaSenha123!` (alterar em produção)

### Webhook WhatsApp
- Validação HMAC com `WHATSAPP_WEBHOOK_SECRET`
- Mensagens são processadas de forma idempotente (hash SHA256)

---

## 8. Comandos úteis

```bash
# Verificar se o backend está rodando
curl http://localhost:8000/docs

# Verificar se o Ollama está rodando
curl http://localhost:11434/api/tags

# Verificar se o Redis está rodando
redis-cli ping

# Listar modelos Ollama
ollama list

# Baixar modelo
ollama pull llama3.2:1b

# Executar seed da planilha
cd backend && python -m src.infrastructure.sheets.seed

# Verificar logs do Celery
docker compose logs celery-worker