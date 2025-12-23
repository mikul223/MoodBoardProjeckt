from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from database import engine
import logging
import time
import sys

logger = logging.getLogger(__name__)


def wait_for_db():
    max_retries = 30
    retry_delay = 1

    for i in range(max_retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ База данных доступна")
            return True
        except OperationalError as e:
            logger.warning(f"База данных недоступна, попытка {i + 1}/{max_retries}")
            time.sleep(retry_delay)

    logger.error("❌ Не удалось подключиться к базе данных")
    return False


def remove_unused_columns(conn):
    try:
        logger.info("Удаление ненужных столбцов...")

        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS created_at CASCADE"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS updated_at CASCADE"))
        logger.info("✅ Удалены created_at, updated_at из users")

        conn.execute(text("ALTER TABLE boards DROP COLUMN IF EXISTS updated_at CASCADE"))
        logger.info("✅ Удален updated_at из boards")

        conn.execute(text("ALTER TABLE board_members DROP COLUMN IF EXISTS invited_at CASCADE"))
        logger.info("✅ Удален invited_at из board_members")

        return True

    except Exception as e:
        logger.error(f"Ошибка при удалении столбцов: {e}")
        return False


def convert_to_bigint(conn):
    try:
        logger.info("Конвертация типов данных в BIGINT...")

        alter_commands = [
            "ALTER TABLE users ALTER COLUMN id TYPE BIGINT",
            "ALTER TABLE boards ALTER COLUMN id TYPE BIGINT",
            "ALTER TABLE boards ALTER COLUMN owner_id TYPE BIGINT",
            "ALTER TABLE board_members ALTER COLUMN board_id TYPE BIGINT",
            "ALTER TABLE board_members ALTER COLUMN user_id TYPE BIGINT",
            "ALTER TABLE content_items ALTER COLUMN id TYPE BIGINT",
            "ALTER TABLE content_items ALTER COLUMN board_id TYPE BIGINT",
            "ALTER TABLE content_items ALTER COLUMN created_by TYPE BIGINT",
        ]

        sequence_commands = [
            "ALTER SEQUENCE IF EXISTS users_id_seq AS BIGINT",
            "ALTER SEQUENCE IF EXISTS boards_id_seq AS BIGINT",
            "ALTER SEQUENCE IF EXISTS content_items_id_seq AS BIGINT",
        ]

        for cmd in alter_commands + sequence_commands:
            try:
                conn.execute(text(cmd))
                logger.info(f"Выполнено: {cmd}")
            except Exception as e:
                logger.warning(f"Не удалось выполнить {cmd}: {e}")

        return True

    except Exception as e:
        logger.error(f"Ошибка при конвертации в BIGINT: {e}")
        return False


def update_board_members_constraint(conn):
    try:
        logger.info("Обновление CheckConstraint для board_members...")

        conn.execute(text("ALTER TABLE board_members ALTER COLUMN role TYPE VARCHAR(15)"))
        logger.info("✅ Поле role расширено до VARCHAR(15)")

        conn.execute(text("UPDATE board_members SET role = 'owner' WHERE role = 'creator'"))
        logger.info("✅ Записи 'creator' обновлены на 'owner'")

        conn.execute(text("ALTER TABLE board_members DROP CONSTRAINT IF EXISTS check_role_values"))

        conn.execute(text("""
                          ALTER TABLE board_members
                              ADD CONSTRAINT check_role_values
                                  CHECK (role IN ('owner', 'collaborator', 'editor', 'viewer'))
                          """))

        logger.info("✅ CheckConstraint обновлен с ролью 'collaborator'")
        return True

    except Exception as e:
        logger.error(f"Ошибка при обновлении CheckConstraint: {e}")
        return False


def migrate_collaborators_to_board_members(conn):
    try:
        logger.info("Перенос соавторов из board_collaborators в board_members...")

        result = conn.execute(text("""
                                   SELECT EXISTS (SELECT 1
                                                  FROM information_schema.tables
                                                  WHERE table_name = 'board_collaborators')
                                   """)).fetchone()

        if result and result[0]:
            logger.info("Добавление владельцев в board_members...")
            conn.execute(text("""
                              INSERT INTO board_members (board_id, user_id, role)
                              SELECT id, owner_id, 'owner'
                              FROM boards
                              WHERE owner_id IS NOT NULL
                                AND NOT EXISTS (SELECT 1
                                                FROM board_members bm
                                                WHERE bm.board_id = boards.id
                                                  AND bm.user_id = boards.owner_id)
                              """))

            logger.info("Перенос соавторов в board_members...")
            conn.execute(text("""
                              INSERT INTO board_members (board_id, user_id, role)
                              SELECT board_id, user_id, 'collaborator'
                              FROM board_collaborators
                              WHERE NOT EXISTS (SELECT 1
                                                FROM board_members bm
                                                WHERE bm.board_id = board_collaborators.board_id
                                                  AND bm.user_id = board_collaborators.user_id)
                              """))

            logger.info("Удаление таблицы board_collaborators...")
            conn.execute(text("DROP TABLE board_collaborators CASCADE"))
            logger.info("✅ Таблица board_collaborators удалена")
        else:
            logger.info("✅ Таблица board_collaborators не существует, пропускаем миграцию")

        return True

    except Exception as e:
        logger.error(f"Ошибка при переносе соавторов: {e}")
        return False


def add_z_index_column(conn):
    try:
        logger.info("Проверяем наличие колонки z_index в таблице content_items...")

        result = conn.execute(text("""
                                   SELECT column_name
                                   FROM information_schema.columns
                                   WHERE table_name = 'content_items'
                                     AND column_name = 'z_index'
                                   """)).fetchone()

        if not result:
            logger.info("Добавляю колонку z_index в таблицу content_items...")
            conn.execute(text("""
                              ALTER TABLE content_items
                                  ADD COLUMN z_index INTEGER DEFAULT 1
                              """))
            logger.info("✅ Колонка z_index добавлена в таблицу content_items")
        else:
            logger.info("✅ Колонка z_index уже существует в таблице content_items")

        return True

    except Exception as e:
        logger.error(f"Ошибка при добавлении колонки z_index: {e}")
        return False


def add_board_settings_columns(conn):
    try:
        logger.info("Добавление колонок для настроек доски...")

        new_columns = [
            {
                "name": "border_color",
                "type": "VARCHAR(20)",
                "default": "'#5D4037'",
                "check": "CHECK (border_color ~ '^#[0-9A-Fa-f]{3,6}$')"
            },
            {
                "name": "background_color",
                "type": "VARCHAR(20)",
                "default": "'#FFFBF0'",
                "check": "CHECK (background_color ~ '^#[0-9A-Fa-f]{3,6}$')"
            },
            {
                "name": "board_width",
                "type": "INTEGER",
                "default": "1200",
                "check": "CHECK (board_width >= 400 AND board_width <= 2500)"
            },
            {
                "name": "board_height",
                "type": "INTEGER",
                "default": "900",
                "check": "CHECK (board_height >= 300 AND board_height <= 2000)"
            }
        ]

        for column in new_columns:
            result = conn.execute(text(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'boards'
                    AND column_name = '{column["name"]}'
            """)).fetchone()

            if not result:
                logger.info(f"Добавляю колонку {column['name']} в таблицу boards...")

                sql = f"""
                    ALTER TABLE boards
                    ADD COLUMN {column["name"]} {column["type"]} DEFAULT {column["default"]}
                """
                conn.execute(text(sql))

                if "check" in column:
                    try:
                        constraint_name = f"check_{column['name']}"
                        check_sql = f"""
                            ALTER TABLE boards
                            ADD CONSTRAINT {constraint_name} {column["check"]}
                        """
                        conn.execute(text(check_sql))
                        logger.info(f"  Добавлен CHECK constraint для {column['name']}")
                    except Exception as e:
                        logger.warning(f"  Не удалось добавить CHECK constraint для {column['name']}: {e}")

                logger.info(f"✅ Колонка {column['name']} добавлена в таблицу boards")
            else:
                logger.info(f"✅ Колонка {column['name']} уже существует в таблице boards")

        logger.info("Обновление существующих записей с настройками по умолчанию...")
        conn.execute(text("""
                          UPDATE boards
                          SET border_color     = '#5D4037',
                              background_color = '#FFFBF0',
                              board_width      = 1200,
                              board_height     = 900
                          WHERE border_color IS NULL
                             OR background_color IS NULL
                             OR board_width IS NULL
                             OR board_height IS NULL
                          """))

        for column in new_columns:
            try:
                conn.execute(text(f"""
                    ALTER TABLE boards
                    ALTER COLUMN {column["name"]} SET NOT NULL
                """))
                logger.info(f"  Установлен NOT NULL constraint для {column['name']}")
            except Exception as e:
                logger.warning(f"  Не удалось установить NOT NULL constraint для {column['name']}: {e}")

        logger.info("✅ Все колонки для настроек доски добавлены и обновлены")
        return True

    except Exception as e:
        logger.error(f"Ошибка при добавлении колонок настроек доски: {e}")
        return False


def update_background_color_default(conn):
    try:
        logger.info("Обновление значения по умолчанию для background_color...")

        result = conn.execute(text("""
                                   SELECT column_default
                                   FROM information_schema.columns
                                   WHERE table_name = 'boards'
                                     AND column_name = 'background_color'
                                   """)).fetchone()

        if result and result[0]:
            current_default = result[0].lower()
            if "'#ffffff'" in current_default or "ffffff" in current_default:
                logger.info("Обновляю значение по умолчанию с #ffffff на #FFFBF0...")

                conn.execute(text("""
                                  ALTER TABLE boards
                                      ALTER COLUMN background_color DROP DEFAULT
                                  """))

                conn.execute(text("""
                                  ALTER TABLE boards
                                      ALTER COLUMN background_color SET DEFAULT '#FFFBF0'
                                  """))

                conn.execute(text("""
                                  UPDATE boards
                                  SET background_color = '#FFFBF0'
                                  WHERE background_color = '#ffffff'
                                  """))

                logger.info("✅ Значение по умолчанию для background_color обновлено на #FFFBF0")
            else:
                logger.info(f"✅ Значение по умолчанию уже установлено: {result[0]}")
        else:
            logger.info("✅ Колонка background_color не найдена или не имеет значения по умолчанию")

        return True

    except Exception as e:
        logger.error(f"Ошибка при обновлении значения по умолчанию: {e}")
        return False


def create_indexes(conn):
    try:
        logger.info("Создание индексов...")

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_website_login ON users(website_login)",
            "CREATE INDEX IF NOT EXISTS idx_boards_owner_id ON boards(owner_id)",
            "CREATE INDEX IF NOT EXISTS idx_boards_board_code ON boards(board_code)",
            "CREATE INDEX IF NOT EXISTS idx_boards_view_token ON boards(view_token)",
            "CREATE INDEX IF NOT EXISTS idx_content_items_board_id ON content_items(board_id)",
            "CREATE INDEX IF NOT EXISTS idx_content_items_type ON content_items(type)",
            "CREATE INDEX IF NOT EXISTS idx_content_items_z_index ON content_items(z_index)",
            "CREATE INDEX IF NOT EXISTS idx_board_members_board_user ON board_members(board_id, user_id)",
            "CREATE INDEX IF NOT EXISTS idx_board_members_role ON board_members(role)",
        ]

        for index_sql in indexes:
            try:
                conn.execute(text(index_sql))
            except Exception as e:
                logger.warning(f"Не удалось создать индекс: {e}")

        logger.info("✅ Индексы созданы")
        return True

    except Exception as e:
        logger.error(f"Ошибка при создании индексов: {e}")
        return False


def run_migrations():
    if not wait_for_db():
        logger.error("Не удалось выполнить миграции: база данных недоступна")
        return False

    try:
        logger.info("Начинаю выполнение миграций для обновления структуры БД...")

        with engine.connect() as conn:
            trans = conn.begin()

            try:
                convert_to_bigint(conn)

                remove_unused_columns(conn)

                update_board_members_constraint(conn)

                migrate_collaborators_to_board_members(conn)

                add_z_index_column(conn)

                add_board_settings_columns(conn)

                update_background_color_default(conn)

                create_indexes(conn)

                trans.commit()
                logger.info("✅ Все миграции успешно выполнены")
                return True

            except Exception as e:
                trans.rollback()
                logger.error(f"❌ Ошибка при выполнении миграций: {e}", exc_info=True)
                return False

    except Exception as e:
        logger.error(f"❌ Ошибка подключения к базе данных: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Запуск миграций базы данных MoodBoard")
    print("=" * 60)
    print("Новые функции в этой миграции:")
    print("1. Добавлены колонки для настроек доски:")
    print("   - border_color (цвет рамки)")
    print("   - background_color (цвет фона)")
    print("   - board_width (ширина доски)")
    print("   - board_height (высота доски)")
    print("2. Обновлен background_color по умолчанию с #ffffff на #FFFBF0")
    print("=" * 60)

    print("\nЗапуск миграций...")
    success = run_migrations()

    if success:
        print("\n" + "=" * 60)
        print("✅ Миграции успешно завершены!")
        print("Новая структура таблицы boards:")
        print("  • border_color VARCHAR(20) DEFAULT '#5D4037'")
        print("  • background_color VARCHAR(20) DEFAULT '#FFFBF0'")
        print("  • board_width INTEGER DEFAULT 1200")
        print("  • board_height INTEGER DEFAULT 900")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ Ошибка при выполнении миграций!")
        print("=" * 60)
        sys.exit(1)