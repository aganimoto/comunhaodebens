"""Inicializa abas e configuração padrão na planilha.

ATENÇÃO: Este script NÃO recria abas que já existem na planilha.
Ele apenas adiciona cabeçalhos se as abas estiverem vazias
e popula a aba Configuração com valores padrão (se vazia).

Estrutura atual (Fase 5 — extração via regex, sem IA):
- ``Doações``: aba principal, sem Hora/Tipo Documento (não extraídos)
- ``Registros``: mantido por retrocompatibilidade
"""
from src.infrastructure.sheets.config_reader import DEFAULTS
from src.infrastructure.sheets.sheets_client import SheetsClient

SHEETS = [
    ("Membros", ["Telefone", "Nome", "Categoria", "Ativo"]),
    (
        "Doações",
        [
            "Protocolo",
            "Data",
            "Nome",
            "Categoria",
            "Valor",
            "Favorecido",
            "Telefone",
            "Status",
            "Confiança",
            "OCR Preview",
        ],
    ),
    (
        "Registros",
        [
            "Protocolo",
            "Data",
            "Nome",
            "Categoria",
            "Valor",
            "Telefone",
            "Status",
            "Confiança",
        ],
    ),
    ("Pendências", ["ID", "Data", "Telefone", "Nome", "Motivo", "Status", "Observação"]),
    ("Auditoria", ["Timestamp", "Evento", "Detalhes"]),
    ("Configuração", ["Chave", "Valor"]),
    ("Dashboard", ["Indicador", "Valor"]),
]


def seed_spreadsheet() -> None:
    client = SheetsClient()
    if not client.available:
        raise RuntimeError("Google Sheets não configurado (credenciais ou SPREADSHEET_ID)")

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    from src.config import get_settings

    settings = get_settings()
    if not settings.google_service_account_json:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON não configurado")

    creds = service_account.Credentials.from_service_account_file(
        settings.google_service_account_json,
        scopes=SheetsClient.SCOPES,
    )
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    meta = service.spreadsheets().get(spreadsheetId=client._spreadsheet_id).execute()
    abas_existentes = {s["properties"]["title"] for s in meta.get("sheets", [])}

    for title, _ in SHEETS:
        if title not in abas_existentes:
            try:
                service.spreadsheets().batchUpdate(
                    spreadsheetId=client._spreadsheet_id,
                    body={
                        "requests": [
                            {
                                "addSheet": {
                                    "properties": {"title": title},
                                }
                            }
                        ]
                    },
                ).execute()
                print(f"  Aba '{title}' criada.")
            except Exception as e:
                print(f"  Aba '{title}' já existe ou erro: {e}")

    for title, headers in SHEETS:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=client._spreadsheet_id, range=f"{title}!A1:Z")
            .execute()
        )
        values = result.get("values", [])
        if not values:
            client.append_row(title, headers)
            print(f"  Cabeçalhos adicionados em '{title}'.")

    config_rows = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=client._spreadsheet_id, range="Configuração!A2:B")
        .execute()
    )
    config_values = config_rows.get("values", [])
    if not config_values:
        for chave, valor in DEFAULTS.items():
            client.append_row("Configuração", [chave, valor])
        print(f"  {len(DEFAULTS)} configurações padrão inseridas.")
    else:
        print(f"  Configuração já possui {len(config_values)} linha(s). Nenhum dado inserido.")

    print("\nSeed concluído com sucesso!")