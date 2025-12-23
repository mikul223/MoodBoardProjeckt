import os
import logging
import sys
import time
from redis import Redis
from rq import Worker, Queue, Connection
from dotenv import load_dotenv

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://:redispass123@redis:6379")
logger.info(f"Используем Redis URL: {REDIS_URL.replace('redispass123', '******')}")


def create_redis_connection():
    return Redis.from_url(
        REDIS_URL,
        socket_connect_timeout=300,
        socket_timeout=300,
        socket_keepalive=True,
        health_check_interval=60,
        decode_responses=True,
        retry_on_timeout=True
    )


def wait_for_redis(max_retries=10):
    for i in range(max_retries):
        try:
            redis_conn = create_redis_connection()
            if redis_conn.ping():
                logger.info("✅ Redis подключен успешно")
                return redis_conn
            else:
                logger.warning(f"Redis ping не прошел, попытка {i + 1}/{max_retries}")
        except Exception as e:
            logger.warning(f"Ошибка подключения к Redis, попытка {i + 1}/{max_retries}: {e}")

        if i < max_retries - 1:
            time.sleep(3)

    logger.error("❌ Не удалось подключиться к Redis после всех попыток")
    return None


if __name__ == '__main__':
    logger.info("🚀 Запуск worker...")

    max_worker_restarts = 5
    restart_count = 0

    while restart_count < max_worker_restarts:
        try:
            redis_conn = wait_for_redis()
            if not redis_conn:
                logger.error("Не могу запустить worker без Redis")
                time.sleep(5)
                restart_count += 1
                continue

            logger.info(f"Worker запущен (попытка {restart_count + 1}/{max_worker_restarts})")

            with Connection(redis_conn):
                worker = Worker(['default'])
                worker.work()

        except Exception as e:
            restart_count += 1
            logger.error(f"Worker упал с ошибкой: {type(e).__name__}: {e}")

            if restart_count < max_worker_restarts:
                logger.info(f"Перезапуск через 5 секунд...")
                time.sleep(5)
            else:
                logger.error(f"Worker остановлен после {max_worker_restarts} перезапусков")
                break

    logger.info("Worker завершил работу")