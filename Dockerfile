# Lean, reproducible runtime image for the public read-only API.
FROM python:3.13.1-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HEATSAFE_ENVIRONMENT=production \
    HEATSAFE_HOST=0.0.0.0 \
    HEATSAFE_PORT=7860 \
    HEATSAFE_PUBLISHED_DIR=ml/data/published

WORKDIR /app

RUN addgroup --system heatsafe && adduser --system --ingroup heatsafe heatsafe
RUN apt-get update \
    && apt-get install --no-install-recommends --yes libexpat1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY --chown=heatsafe:heatsafe backend ./backend
COPY --chown=heatsafe:heatsafe ml/src ./ml/src
COPY --chown=heatsafe:heatsafe ml/configs ./ml/configs
RUN mkdir -p ml/data/published /home/heatsafe \
    && chown -R heatsafe:heatsafe /app /home/heatsafe

ENV HOME=/home/heatsafe \
    XDG_CACHE_HOME=/home/heatsafe/.cache
USER heatsafe
EXPOSE 7860

# The bundle is restored from the configured Hugging Face dataset before the API accepts traffic.
# Tokens and database credentials are supplied only by the deployment platform's secret manager.
CMD ["sh", "-c", "python -m ml.src.sync.storage restore-bundle && exec uvicorn backend.core.apis.api:app --host 0.0.0.0 --port ${HEATSAFE_PORT:-7860}"]
