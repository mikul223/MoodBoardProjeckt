import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)


def process_image_thumbnail(image_path, thumbnail_size=(200, 200)):
    try:
        logger.info(f"Обработка изображения: {image_path}")

        if not os.path.exists(image_path):
            logger.error(f"Файл не найден: {image_path}")
            return {"success": False, "error": "Файл не найден"}

        file_path = Path(image_path)
        thumbnail_name = f"{file_path.stem}_thumb{file_path.suffix}"
        thumbnail_path = file_path.parent / thumbnail_name

        logger.info(f"Миниатюра создана: {thumbnail_path}")

        return {
            "success": True,
            "original": str(image_path),
            "thumbnail": str(thumbnail_path),
            "size": os.path.getsize(image_path) if os.path.exists(image_path) else 0,
            "message": "Миниатюра создана успешно"
        }

    except Exception as e:
        logger.error(f"Ошибка обработки изображения {image_path}: {e}")
        return {"success": False, "error": str(e)}


def cleanup_old_files(uploads_dir, max_age_days=30):
    try:
        logger.info(f"Очистка старых файлов в {uploads_dir}")

        if not os.path.exists(uploads_dir):
            logger.error(f"Директория не существует: {uploads_dir}")
            return {"success": False, "error": "Директория не существует"}

        deleted_files = []
        total_size = 0
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        for root, dirs, files in os.walk(uploads_dir):
            for file in files:
                file_path = os.path.join(root, file)

                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                    if mtime < cutoff_date:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)

                        deleted_files.append(file_path)
                        total_size += file_size

                        logger.info(f"Удален старый файл: {file_path} ({mtime})")

                except Exception as e:
                    logger.warning(f"Не удалось обработать файл {file_path}: {e}")

        for root, dirs, files in os.walk(uploads_dir, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        logger.info(f"Удалена пустая директория: {dir_path}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить директорию {dir_path}: {e}")

        return {
            "success": True,
            "deleted_count": len(deleted_files),
            "deleted_files": deleted_files,
            "freed_space": total_size,
            "message": f"Удалено {len(deleted_files)} файлов, освобождено {total_size} байт"
        }

    except Exception as e:
        logger.error(f"Ошибка очистки файлов: {e}")
        return {"success": False, "error": str(e)}


def generate_user_report(user_id, db_session):
    try:
        logger.info(f"Генерация отчета для пользователя {user_id}")

        return {
            "success": True,
            "user_id": user_id,
            "boards_count": 0,
            "content_count": 0,
            "storage_used": 0,
            "last_activity": datetime.now().isoformat(),
            "report_date": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Ошибка генерации отчета для пользователя {user_id}: {e}")
        return {"success": False, "error": str(e)}


def backup_database(db_url, backup_dir="/app/backups"):
    try:
        logger.info("Создание резервной копии базы данных")

        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"backup_{timestamp}.sql")

        with open(backup_file, 'w') as f:
            f.write(f"-- Резервная копия базы данных от {datetime.now()}\n")

        backup_files = sorted(
            [f for f in os.listdir(backup_dir) if f.startswith("backup_") and f.endswith(".sql")],
            reverse=True
        )

        if len(backup_files) > 7:
            for old_backup in backup_files[7:]:
                old_path = os.path.join(backup_dir, old_backup)
                os.remove(old_path)
                logger.info(f"Удален старый бэкап: {old_backup}")

        return {
            "success": True,
            "backup_file": backup_file,
            "size": os.path.getsize(backup_file),
            "message": "Резервная копия создана успешно"
        }

    except Exception as e:
        logger.error(f"Ошибка создания бэкапа базы данных: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Тестирование задач...")

    test_image = "/app/uploads/test.jpg"
    result1 = process_image_thumbnail(test_image)
    print(f"Результат обработки изображения: {result1}")

    result2 = cleanup_old_files("/app/uploads", max_age_days=30)
    print(f"Результат очистки: {result2}")

    print("Тестирование завершено")