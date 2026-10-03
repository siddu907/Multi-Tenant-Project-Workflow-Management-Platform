from app.background import scheduler


def test_application_lifespan_registers_daily_deadline_job(client):
    assert scheduler._scheduler is not None
    job = scheduler._scheduler.get_job("daily-deadline-notifications")
    assert job is not None
    assert "hour='0'" in str(job.trigger)
    assert "minute='0'" in str(job.trigger)
