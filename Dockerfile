FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

RUN python manage.py collectstatic --noinput 2>/dev/null || true
RUN python manage.py migrate --noinput

EXPOSE 8000

CMD ["gunicorn", "blogcopier.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
