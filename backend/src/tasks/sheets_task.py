from src.tasks.celery_app import celery_app


@celery_app.task(name="sync_sheets_registro")
def sync_sheets_registro(payload: dict) -> dict:
    from src.infrastructure.sheets.sheets_writer import SheetsWriter

    writer = SheetsWriter()
    writer.append_registro(**payload)
    return {"ok": True}
