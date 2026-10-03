from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.background.deadline_notifications import create_deadline_notifications
from app.database import SessionLocal

_scheduler: BackgroundScheduler | None = None


def _run_deadline_notifications() -> None:
    with SessionLocal() as db:
        create_deadline_notifications(db, today=datetime.now(timezone.utc).date())


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_deadline_notifications,
        trigger="cron",
        hour=0,
        minute=0,
        id="daily-deadline-notifications",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
