FROM python:3.12-slim

RUN useradd -r -s /usr/sbin/nologin appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard ./dashboard

WORKDIR /app/dashboard

RUN python manage.py collectstatic --noinput 2>/dev/null || true

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Use UvicornWorker so Gunicorn can serve async Django ASGI views correctly.
CMD ["gunicorn", "config.asgi:application", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--timeout", "30"]
