import re
import logging
from functools import wraps
from typing import Any, Dict, List, Optional, Union
from sqlalchemy.orm import Session, Query
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class SafeDB:
    @staticmethod
    def safe_filter(query: Query, model: Any, **filters) -> Query:
        for key, value in filters.items():
            if hasattr(model, key):
                sanitized_value = SafeDB.sanitize_value(value)
                if sanitized_value is not None:
                    query = query.filter(getattr(model, key) == sanitized_value)
        return query

    @staticmethod
    def safe_like(query: Query, model: Any, field_name: str, pattern: str) -> Query:
        if hasattr(model, field_name):
            pattern = pattern.replace('%', '\\%').replace('_', '\\_')
            pattern = re.sub(r'[\'\";\\-\\-]', '', pattern)
            query = query.filter(getattr(model, field_name).like(f'%{pattern}%'))
        return query

    @staticmethod
    def safe_raw_query(db: Session, sql: str, params: Optional[Dict] = None) -> Any:
        if not SafeDB.is_safe_sql(sql):
            logger.error(f"Попытка выполнить опасный SQL запрос: {sql[:100]}...")
            raise ValueError("Запрещенный SQL запрос")

        safe_params = {}
        if params:
            for key, value in params.items():
                safe_params[key] = SafeDB.sanitize_value(value)

        try:
            return db.execute(text(sql), safe_params or {})
        except SQLAlchemyError as e:
            logger.error(f"Ошибка выполнения SQL запроса: {e}")
            raise

    @staticmethod
    def sanitize_value(value: Any) -> Any:
        if value is None:
            return None

        if isinstance(value, str):
            is_board_code = False

            if re.match(r'^[A-Z]{3}-[A-Z0-9]{3}-\d{3}$', value):
                is_board_code = True
            elif re.match(r'^[A-Z]{3}[A-Z0-9]{3}\d{3}$', value):
                is_board_code = True

            if is_board_code:
                logger.debug(f"Обнаружен код доски: {value}, пропускаем санитизацию дефисов")
                value = re.sub(r'[\'\";\\\\]', '', value)
            else:
                value = re.sub(r'[\'\";\\-\\-]', '', value)

            dangerous_patterns = [
                r'(?i)\bOR\b.*\b1\b.*\b=\b.*\b1\b',
                r'(?i)\bUNION\b.*\bSELECT\b',
                r'(?i)\bDROP\b.*\bTABLE\b',
                r'(?i)\bDELETE\b.*\bFROM\b',
                r'(?i)\bINSERT\b.*\bINTO\b',
                r'(?i)\bUPDATE\b.*\bSET\b',
            ]

            for pattern in dangerous_patterns:
                if re.search(pattern, value):
                    logger.warning(f"Обнаружена потенциальная SQL инъекция: {value[:50]}...")
                    return ""

            if len(value) > 10000:
                logger.warning(f"Слишком длинное значение: {len(value)} символов")
                return value[:10000]

            return value

        elif isinstance(value, (int, float, bool)):
            return value

        elif isinstance(value, (list, tuple)):
            return [SafeDB.sanitize_value(item) for item in value]

        elif isinstance(value, dict):
            return {k: SafeDB.sanitize_value(v) for k, v in value.items()}

        else:
            return value

    @staticmethod
    def sanitize_value_with_context(value: Any, context: str = "default") -> Any:
        if isinstance(value, str):
            if context == "board_code":
                value = re.sub(r'[\'\";\\\\]', '', value)
                return value
            elif context == "telegram_username":
                value = re.sub(r'[^\w]', '', value)
                return value
            elif context == "filename":
                value = re.sub(r'[\\/:\*\?"<>\|]', '', value)
                return value
            else:
                return SafeDB.sanitize_value(value)
        else:
            return SafeDB.sanitize_value(value)

    @staticmethod
    def is_safe_sql(sql: str) -> bool:
        sql_upper = sql.upper()

        dangerous_keywords = [
            'DROP TABLE', 'DROP DATABASE', 'TRUNCATE TABLE',
            'ALTER TABLE', 'DROP COLUMN', 'ALTER COLUMN',
            'GRANT ALL', 'REVOKE ALL', 'CREATE USER',
            'DROP USER', 'EXECUTE', 'EXEC', 'XP_',
            'SHUTDOWN', 'KILL'
        ]

        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                logger.warning(f"Обнаружено опасное ключевое слово: {keyword}")
                return False

        if '--' in sql or '/*' in sql:
            logger.warning("Обнаружены SQL комментарии")
            return False

        if "'" in sql and ('OR' in sql_upper or 'AND' in sql_upper):
            if not ('%(' in sql or ':%' in sql or '?' in sql or '$' in sql):
                logger.warning("Подозрительное использование кавычек в SQL")
                return False

        return True

    @staticmethod
    def validate_model_fields(model: Any, fields: List[str]) -> bool:
        inspector = inspect(model)
        model_fields = [column.key for column in inspector.columns]

        for field in fields:
            if field not in model_fields:
                logger.warning(f"Поле {field} не существует в модели {model.__name__}")
                return False

        return True


def sanitize_input(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__.lower()
        context = "default"

        if 'board_code' in func_name or 'board' in func_name:
            context = "board_code"
        elif 'username' in func_name or 'telegram' in func_name:
            context = "telegram_username"
        elif 'file' in func_name or 'upload' in func_name:
            context = "filename"

        new_kwargs = {}
        for key, value in kwargs.items():
            arg_context = context
            if 'board_code' in key.lower():
                arg_context = "board_code"
            elif 'username' in key.lower() or 'telegram' in key.lower():
                arg_context = "telegram_username"
            elif 'file' in key.lower() or 'filename' in key.lower():
                arg_context = "filename"

            new_kwargs[key] = SafeDB.sanitize_value_with_context(value, arg_context)

        new_args = []
        for arg in args:
            if isinstance(arg, str):
                new_args.append(SafeDB.sanitize_value_with_context(arg, context))
            else:
                new_args.append(arg)

        return func(*new_args, **new_kwargs)

    return wrapper


def validate_sql_input(value: str) -> bool:
    if not isinstance(value, str):
        return False

    value_upper = value.upper()

    patterns = [
        r"'\s*OR\s*'.*'",
        r"'\s*OR\s*\d+\s*=\s*\d+",
        r"'\s*AND\s*\d+\s*=\s*\d+",
        r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER)",
        r"UNION\s+SELECT",
        r"SELECT\s+.*FROM",
        r"INSERT\s+INTO",
        r"UPDATE\s+.*SET",
        r"DELETE\s+FROM",
        r"--\s*$",
        r"\/\*.*\*\/",
        r"EXEC\s*\(|EXECUTE\s*\(",
        r"XP_",
        r"WAITFOR\s+DELAY",
        r"BENCHMARK\s*\(",
        r"SLEEP\s*\(",
        r"PG_SLEEP",
        r"DROP\s+(TABLE|DATABASE|SCHEMA)",
        r"TRUNCATE\s+TABLE",
        r"GRANT\s+ALL",
        r"CREATE\s+USER",
    ]

    for pattern in patterns:
        if re.search(pattern, value_upper, re.IGNORECASE | re.DOTALL):
            logger.warning(f"Обнаружена потенциальная SQL инъекция: {value[:100]}")
            return True

    quote_operator_patterns = [
        r"'.*\s+(OR|AND)\s+.*'",
        r"'.*\s+(=|!=|<>|>|<|>=|<=)\s+.*'"
    ]

    for pattern in quote_operator_patterns:
        if re.search(pattern, value_upper):
            logger.warning(f"Подозрительное использование кавычек с операторами: {value[:100]}")
            return True

    return False


def log_suspicious_activity(ip_address: str, user_id: Optional[int],
                            endpoint: str, suspicious_data: str,
                            action: str = "sql_injection_attempt"):
    logger.warning(
        f"🔴 ПОДОЗРИТЕЛЬНАЯ АКТИВНОСТЬ: "
        f"IP={ip_address}, "
        f"UserID={user_id}, "
        f"Endpoint={endpoint}, "
        f"Action={action}, "
        f"Data={suspicious_data[:200]}"
    )