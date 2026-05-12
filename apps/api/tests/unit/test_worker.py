"""Smoke test del worker ARQ — verifica configuración sin arrancar Redis."""


def test_worker_settings_queue_name():
    from worker.main import WorkerSettings

    assert WorkerSettings.queue_name == "mailflow:default"


def test_worker_settings_has_process_function():
    from worker.main import WorkerSettings, process_account_cycle

    assert process_account_cycle in WorkerSettings.functions


def test_worker_settings_has_cron():
    from worker.main import WorkerSettings, schedule_cycles

    assert len(WorkerSettings.cron_jobs) == 1
    cron_job = WorkerSettings.cron_jobs[0]
    assert cron_job.coroutine is schedule_cycles
