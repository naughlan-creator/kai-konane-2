# syntax=docker/dockerfile:1

# builder
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN printf 'precedence ::ffff:0:0/96  100\n' >> /etc/gai.conf
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir \
        --retries 5 --timeout 30 \
        -r requirements.txt

# runtime
FROM python:3.12-slim AS runtime

# Tells a registry which repository built this image. GHCR uses it to link
# the package to the repo automatically -- without it the packages exist but
# do not appear on the repo page, and have to be connected by hand.
LABEL org.opencontainers.image.source="https://github.com/naughlan-creator/kai-konane-2" \
      org.opencontainers.image.description="The domain and the database. JSON only." \
      org.opencontainers.image.licenses="MIT"


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=appuser:appuser . .

RUN mkdir -p /app/static/images /app/instance && \
    chown -R appuser:appuser /app/static /app/instance

USER appuser
EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", \
     "--timeout", "60", "--access-logfile", "-", "app:create_app()"]