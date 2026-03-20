from worker import worker


@worker.task(bind=True, max_retries=0)
def process_job(self, job_id: int) -> int:
    """Worker runs this when FastAPI calls process_job.delay(job_id)."""
    # Do work here
    return job_id
