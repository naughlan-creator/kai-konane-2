# syntax=docker/dockerfile:1
FROM python:3.12-alpine

# Tells a registry which repository built this image. GHCR uses it to link
# the package to the repo automatically -- without it the packages exist but
# do not appear on the repo page, and have to be connected by hand.
LABEL org.opencontainers.image.source="https://github.com/naughlan-creator/kai-konane-2" \
      org.opencontainers.image.description="The UI. Templates and sessions, no ORM." \
      org.opencontainers.image.licenses="MIT"


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

RUN apk add --no-cache curl

RUN adduser -D -u 10001 appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

USER appuser
EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", \
     "--timeout", "30", "--access-logfile", "-", "app:create_app()"]