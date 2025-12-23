FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

CMD ["python", "simple_worker.py"]