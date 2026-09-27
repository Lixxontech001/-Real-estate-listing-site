# syntax=docker/dockerfile:1
# Multi-stage: build with dev tools, ship only what runtime needs.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=project.settings

WORKDIR /app


# ---------------------------------------------------------------- build stage
FROM base AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ ./requirements/
RUN pip install --upgrade pip && pip install -r requirements/prod.txt


# -------------------------------------------------------------- runtime stage
FROM base AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages \
                     /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Non-root: never run the app as root.
RUN groupadd --system app && useradd --system --gid app --create-home app
WORKDIR /app
COPY --chown=app:app . /app

RUN mkdir -p /app/staticfiles /app/media && chown -R app:app /app/staticfiles /app/media
USER app

# Collect static at build time so the image ships ready to serve.
RUN DJANGO_ENV=prod DJANGO_SECRET_KEY=build-only \
    SECRET_KEY=build-only \
    DATABASE_URL=postgres://build:build@localhost:5432/build \
    NOMINATIM_USER_AGENT=build python manage.py collectstatic --noinput

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

# 3 workers is a reasonable default; scale the container, not the worker count.
CMD ["gunicorn", "project.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
