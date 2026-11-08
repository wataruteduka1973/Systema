# Systema web and scheduler image (Linux). See docs/deployment-linux.md and ADR 0007.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN useradd --system --create-home --uid 10001 systema

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Hashed, compressed static files for WhiteNoise. collectstatic needs no database or secrets,
# so it runs in development mode here; the container runs with the settings from .env.
RUN SYSTEMA_ENV=development DB_ENGINE=sqlite python manage.py collectstatic --noinput \
    && mkdir -p logs .local \
    && chown -R systema:systema logs .local

USER systema

EXPOSE 8000

# WEB_CONCURRENCY sets the worker count; GUNICORN_CMD_ARGS can add other options.
CMD ["gunicorn", "System_Config.wsgi:application", "--bind", "0.0.0.0:8000", "--access-logfile", "-"]
