#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Criado .env a partir de .env.example — edite as senhas antes de produção."
fi

mkdir -p secrets shared/media shared/relatorios shared/backups

echo "Subindo infraestrutura (postgres, redis, ollama)..."
docker compose up -d postgres redis ollama

echo "Aguardando PostgreSQL..."
sleep 5

echo "Subindo backend para migrations..."
docker compose build backend
docker compose run --rm backend alembic upgrade head

echo "Setup concluído. Próximos passos:"
echo "  1. Coloque google_sa.json em secrets/ e configure GOOGLE_SPREADSHEET_ID"
echo "  2. docker compose up -d"
echo "  3. docker compose logs -f whatsapp-service  # escanear QR"
echo "  4. docker compose exec backend python scripts/seed_sheets.py"
