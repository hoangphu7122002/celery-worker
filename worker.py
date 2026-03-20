import ssl
from urllib.parse import urlparse

from celery import Celery
from kombu import Queue

from config import settings

redis_ssl_options = None
if urlparse(settings.redis.url).scheme == "rediss":
    redis_ssl_options = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

worker = Celery(
    "myapp",
    broker=settings.redis.url,
    backend=settings.redis.url,
)
worker.autodiscover_tasks(["tasks"])
import tasks.jobs  # noqa: F401
import tasks.zendesk  # noqa: F401
worker.conf.broker_use_ssl = redis_ssl_options
worker.conf.redis_backend_use_ssl = redis_ssl_options
worker.conf.task_queues = (Queue("celery"),)
