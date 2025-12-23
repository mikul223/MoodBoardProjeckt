FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    postgresql-client \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY src/*.py /app/

RUN mkdir -p uploads/images uploads/texts logs \
    && chmod 755 uploads logs

ENV PYTHONPATH=/app

RUN echo "=== Файлы в /app ===" && ls -la /app/*.py

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]