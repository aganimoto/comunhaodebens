# Operação — CDB Shalom

Guia para a equipe financeira e administradores do sistema.

## Visão geral

O sistema recebe comprovantes de PIX enviados pelo WhatsApp, identifica o
contribuinte pelo número de telefone cadastrado na aba **Membros** do
Google Sheets, extrai valor/data/banco via IA, registra no banco e
replica na planilha.

## Papéis (perfis)

| Perfil | Pode ver | Pode editar |
|--------|----------|-------------|
| `administrador` | tudo | tudo (incluindo admin) |
| `financeiro` | tudo | contribuições, pendências, relatórios |
| `consulta` | tudo | nada |

Crie usuários com:

```bash
docker compose exec backend python scripts/create_admin.py \
    --email novo@cdbshalom.org --senha 'SenhaForte123!' --perfil financeiro
```

## Tarefas diárias automáticas

| Horário (BR) | Tarefa | Local |
|--------------|--------|-------|
| 02:00 | `backup_diario` (pg_dump) | `/shared/backups/backup_YYYYMMDD_HHMMSS.dump` |
| 06:00 (dia 1º) | `gerar_relatorio_mensal` | `/shared/relatorios/relatorio_YYYY-MM.pdf` |

Verifique a saúde do Beat com:

```bash
docker compose logs celery-beat
docker compose exec celery-worker celery -A src.tasks.celery_app inspect ping
```

## Relatórios PDF

### Onde ficam

- **Produção:** `/shared/relatorios/relatorio_YYYY-MM.pdf`
- **Dev:** `backend/dev_data/relatorios/relatorio_YYYY-MM.pdf`

### Como gerar manualmente

1. Acesse o painel → **Relatórios PDF**
2. Clique em **Gerar manualmente**
3. Selecione mês/ano e confirme

ou via API:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@cdbshalom.local","senha":"TroqueEstaSenha123!"}' \
    | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -X POST http://localhost:8000/api/v1/relatorios/gerar-sync \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"ano":2026,"mes":5}'
```

O PDF contém:
- Total arrecadado
- Quantidade de contribuições
- Top categorias
- Top membros
- Tabela detalhada de lançamentos

## Backups

### Onde ficam

- **Produção:** `/shared/backups/`
- **Dev:** `backend/dev_data/backups/`

### Política de retenção

Mantém os **últimos 30 backups** (configurável via `BACKUP_KEEP`).

### Restore

```bash
# 1. Localize o backup desejado
ls -lh /shared/backups/

# 2. Copie para um local temporário
cp /shared/backups/backup_20260601_020000.dump /tmp/restore.dump

# 3. Restaure no Postgres (cuidado: sobrescreve o banco!)
docker compose exec -T postgres pg_restore \
    -U cdb_user -d cdb_shalom --clean --if-exists \
    < /tmp/restore.dump
```

### Disparo manual

```bash
TOKEN=...

curl -X POST http://localhost:8000/api/v1/admin/backup/run \
    -H "Authorization: Bearer $TOKEN"
```

## Pendências

A aba **Pendências** da planilha e a rota `/api/v1/pendencias` expõem
todas as situações que exigem ação manual:

| Motivo | Significado | Ação sugerida |
|--------|-------------|---------------|
| `telefone_nao_cadastrado` | Membro novo / mudou de número | Cadastrar na aba Membros |
| `ocr_baixa_confianca` | OCR com confiança < limiar | Verificar imagem original |
| `ia_baixa_confianca` | IA com confiança < limiar | Conferir valor/data/banco |
| `comprovante_duplicado` | Mesmo hash já processado | Avisar o membro |
| `valor_nao_identificado` | IA não extraiu valor | Pedir novo comprovante |
| `erro_processamento` | Falha técnica | Reenviar |

Para resolver via painel: clique em **Resolver** na linha correspondente.
A descrição é registrada automaticamente como `observacao`.

## Modo DEV (para a equipe)

Se você só quer testar o painel sem configurar Sheets/WhatsApp/Ollama:

```bash
# 1. Suba o stack com perfil dev
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 2. Popular dados de exemplo
docker compose exec backend python scripts/seed_dev_data.py

# 3. Acesse o painel
# http://localhost:5173
# login: admin@cdbshalom.local / TroqueEstaSenha123!
```

Em modo dev:
- Planilha Sheets é substituída por arquivo JSON em `dev_data/sheets.json`
- Respostas da IA são determinísticas (mesmo input → mesmo output)
- Mensagens WhatsApp saem gravadas em `dev_data/whatsapp_outbox.json`
- Backups viram placeholders (sem `pg_dump` real)
- Relatórios PDF vão para `dev_data/relatorios/`

## Limpar dados de dev

```bash
rm -rf backend/dev_data
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart backend
```

## Contatos

- **Administrador do sistema:** <admin@cdbshalom.org>
- **Equipe financeira:** <financeiro@cdbshalom.org>
- **Plantão (emergências):** ver README principal
