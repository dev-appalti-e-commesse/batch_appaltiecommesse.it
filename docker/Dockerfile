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

# Debug: Force rebuild and verify files are copied
RUN echo "BUILD_TIME=$(date)" > /app/build_info.txt

COPY jobs/ ./jobs/
COPY docker/run.sh .

# Debug: Verify checkpoint logs are in the copied files
RUN grep -n "CHECKPOINT" /app/jobs/extract_primus_specialized.py || echo "WARNING: No checkpoints found in extract_primus_specialized.py"

RUN chmod +x run.sh && \
    chmod +x jobs/*.py

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV FONTCONFIG_PATH=/etc/fonts
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

ENTRYPOINT ["/app/run.sh"]