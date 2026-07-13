FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system nails && useradd --system --gid nails --home-dir /app nails

WORKDIR /app

COPY --chown=nails:nails pyproject.toml alembic.ini ./
COPY --chown=nails:nails app ./app
COPY --chown=nails:nails alembic ./alembic

RUN pip install --no-cache-dir .

USER nails

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
