FROM python:3.12.4-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    fonts-dejavu-core \
    fonts-liberation \
    fontconfig \
    libfontconfig1 \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY jobs/ ./jobs/
COPY docker/run.sh .

RUN chmod +x run.sh && \
    chmod +x jobs/*.py

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV FONTCONFIG_PATH=/etc/fonts
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

ENTRYPOINT ["/app/run.sh"]