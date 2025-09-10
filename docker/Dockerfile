FROM python:3.12.4-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY jobs/ ./jobs/
COPY docker/run.sh .

RUN chmod +x run.sh && \
    chmod +x jobs/*.py

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

ENTRYPOINT ["/app/run.sh"]