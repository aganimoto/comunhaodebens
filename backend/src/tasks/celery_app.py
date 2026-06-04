from celery import Celery
from celery.schedules import crontab

from src.config import get_settings

settings = get_settings()

celery_app = Celery(
    "cdb_shalom",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "src.tasks.ocr_task",
        "src.tasks.sheets_task",
        "src.tasks.backup_task",
        "src.tasks.relatorio_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.app_timezone,
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Agendamentos (Celery Beat)
celery_app.conf.beat_schedule = {
    # Relatório mensal: roda no primeiro dia de cada mês às 06:00
    "relatorio-mensal": {
        "task": "gerar_relatorio_mensal",
        "schedule": crontab(day_of_month=1, hour=6, minute=0),
    },
    # Backup diário às 02:00 (horário de Brasília)
    "backup-diario": {
        "task": "backup_diario",
        "schedule": crontab(hour=2, minute=0),
    },
}
