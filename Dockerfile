FROM python:3.11-slim

WORKDIR /app

# Install deps
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy app
COPY config.py worker.py api.py ./
COPY tasks/ tasks/
COPY storage/ storage/
COPY models/ models/
COPY clients/ clients/
COPY services/ services/
COPY lib/ lib/

ENV CELERY_CONCURRENCY=4
CMD ["sh", "-c", "celery -A worker worker -Q celery -l info --concurrency ${CELERY_CONCURRENCY:-4}"]
