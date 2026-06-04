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

Ou crie manualmente:

| Aba | Colunas |
|-----|---------|
| Membros | Telefone, Nome, Categoria, Ativo |
| Registros | Protocolo, Data, Hora, Nome, Categoria, Valor (R$), Banco, Telefone, Status, Confiança (%) |
| Pendências | ID, Data, Hora, Telefone, Nome, Motivo, Status, Observação |
| Auditoria | Timestamp, Evento, Contribuição ID, Telefone, Detalhes |
| Dashboard | (fórmulas — ver spec seção 8) |
| Configuração | Chave, Valor, Descrição |
| Relatórios | Mês, Ano, Data Geração, Caminho Arquivo, Status |

## 5. Categorias válidas

`comunidade_de_vida`, `comunidade_de_alianca`, `obra`, `benfeitor`

## 6. Cache

- Membros: TTL padrão 5 min (`CACHE_MEMBROS_TTL_MIN` na aba Configuração).
- Invalidar: `POST /api/v1/admin/cache/flush` (perfil ADMINISTRADOR).
