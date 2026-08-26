FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY backend/requirements /app/backend/requirements
RUN pip install --upgrade pip && pip install -r /app/backend/requirements/base.txt

FROM base AS development

RUN pip install -r /app/backend/requirements/dev.txt

COPY pyproject.toml /app/pyproject.toml
COPY backend /app/backend
COPY finanzr /app/finanzr

WORKDIR /app/backend

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS production

RUN addgroup --system --gid 10001 finanzr \
    && adduser --system --uid 10001 --ingroup finanzr --home /nonexistent --no-create-home finanzr

COPY --chown=finanzr:finanzr backend /app/backend
COPY --chown=finanzr:finanzr finanzr /app/finanzr

WORKDIR /app/backend

USER finanzr

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
