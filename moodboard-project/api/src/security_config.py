import os
import json
from typing import Dict, List, Any
from datetime import datetime, timedelta


class SecurityConfig:

    def __init__(self):
        self.config = {
            "sql_injection": {
                "enabled": True,
                "block_suspicious": True,
                "log_attempts": True,
                "max_query_length": 10000,
                "dangerous_patterns": [
                    r"'\s*OR\s*'.*'",
                    r"'\s*OR\s*\d+\s*=\s*\d+",
                    r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER)",
                    r"UNION\s+SELECT",
                    r"--\s*$",
                    r"/\*.*\*/",
                    r"EXEC\s*\(",
                    r"XP_",
                    r"DROP\s+(TABLE|DATABASE)"
                ]
            },

            "input_validation": {
                "enabled": True,
                "max_string_length": 10000,
                "min_string_length": 1,
                "allowed_characters": r'[\w\s\-_@\.\,\!\?\:\;\+\=\*\&\^\%\$\#\<\>\(\)\[\]\{\}\|\\\/]',
                "block_html_tags": True,
                "block_script_tags": True
            },

            "password_policy": {
                "min_length": 8,
                "max_length": 50,
                "require_uppercase": True,
                "require_lowercase": True,
                "require_digits": True,
                "require_special_chars": False,
                "max_age_days": 90,
                "history_size": 5
            },

            "jwt": {
                "algorithm": os.getenv("JWT_ALGORITHM", "HS256"),
                "access_token_expire_minutes": int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")),
                "refresh_token_expire_days": 30,
                "issuer": "moodboard-api",
                "audience": "moodboard-users"
            },

            "rate_limiting": {
                "enabled": False,
                "requests_per_minute": 60,
                "requests_per_hour": 1000,
                "block_duration_minutes": 15
            },

            "file_upload": {
                "max_file_size_mb": 10,
                "allowed_extensions": [
                    ".jpg", ".jpeg", ".png", ".gif", ".webp",
                    ".txt", ".pdf", ".doc", ".docx"
                ],
                "allowed_types": ["image", "text"],
                "scan_for_malware": False,
                "max_files_per_user": 1000
            },

            "database_security": {
                "connection_pool_size": 20,
                "max_overflow": 10,
                "pool_timeout": 30,
                "pool_recycle": 3600,
                "isolation_level": "READ_COMMITTED"
            },

            "security_logging": {
                "enabled": True,
                "log_file": "security.log",
                "retention_days": 90,
                "log_level": "WARNING",
                "notify_admins": False
            }
        }

        self.blocked_attempts = 0
        self.blocked_attempts_today = 0
        self.last_reset_date = datetime.now().date()

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self.config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def update(self, key: str, value: Any):
        keys = key.split('.')
        config_level = self.config

        for k in keys[:-1]:
            if k not in config_level:
                config_level[k] = {}
            config_level = config_level[k]

        config_level[keys[-1]] = value

    def increment_blocked_attempts(self):
        self.blocked_attempts += 1

        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.blocked_attempts_today = 0
            self.last_reset_date = current_date

        self.blocked_attempts_today += 1

        if self.blocked_attempts_today >= 10:
            self._log_security_alert("high_blocked_attempts", {
                "attempts_today": self.blocked_attempts_today,
                "total_attempts": self.blocked_attempts
            })

    def get_blocked_attempts(self) -> Dict[str, int]:
        return {
            "total": self.blocked_attempts,
            "today": self.blocked_attempts_today,
            "last_reset": self.last_reset_date.isoformat()
        }

    def validate_input(self, input_data: str, input_type: str = "general") -> Dict[str, Any]:
        result = {
            "valid": True,
            "errors": [],
            "sanitized": input_data
        }

        if not isinstance(input_data, str):
            result["valid"] = False
            result["errors"].append("Input must be a string")
            return result

        max_length = self.get(f"input_validation.max_string_length", 10000)
        if len(input_data) > max_length:
            result["valid"] = False
            result["errors"].append(f"Input too long (max {max_length} characters)")

        if self.get("sql_injection.enabled", True):
            patterns = self.get("sql_injection.dangerous_patterns", [])
            import re
            for pattern in patterns:
                if re.search(pattern, input_data, re.IGNORECASE):
                    result["valid"] = False
                    result["errors"].append("Potential SQL injection detected")
                    self.increment_blocked_attempts()
                    break

        if self.get("input_validation.block_html_tags", True):
            html_patterns = [
                r"<script.*?>.*?</script>",
                r"<.*?on\w+.*?=.*?>",
                r"javascript:",
                r"vbscript:",
                r"expression\s*\(.*?\)"
            ]
            import re
            for pattern in html_patterns:
                if re.search(pattern, input_data, re.IGNORECASE):
                    result["valid"] = False
                    result["errors"].append("Potential XSS attack detected")
                    break

        if not result["valid"]:
            import re
            result["sanitized"] = re.sub(r'[^\w\s\-_@\.\,\!\?\:\;]', '', input_data)
            result["sanitized"] = result["sanitized"][:max_length]

        return result

    def validate_password(self, password: str) -> Dict[str, Any]:
        result = {
            "valid": True,
            "errors": [],
            "strength": "weak"
        }

        policy = self.get("password_policy")

        if len(password) < policy.get("min_length", 8):
            result["valid"] = False
            result["errors"].append(f"Password must be at least {policy['min_length']} characters long")

        if len(password) > policy.get("max_length", 50):
            result["valid"] = False
            result["errors"].append(f"Password must be at most {policy['max_length']} characters long")

        import re

        if policy.get("require_uppercase", True):
            if not re.search(r'[A-Z]', password):
                result["valid"] = False
                result["errors"].append("Password must contain at least one uppercase letter")

        if policy.get("require_lowercase", True):
            if not re.search(r'[a-z]', password):
                result["valid"] = False
                result["errors"].append("Password must contain at least one lowercase letter")

        if policy.get("require_digits", True):
            if not re.search(r'\d', password):
                result["valid"] = False
                result["errors"].append("Password must contain at least one digit")

        if policy.get("require_special_chars", False):
            if not re.search(r'[!@#$%^&*()\-_=+\[\]{}|;:,.<>?]', password):
                result["valid"] = False
                result["errors"].append("Password must contain at least one special character")

        if result["valid"]:
            score = 0
            if len(password) >= 12:
                score += 1
            if re.search(r'[A-Z]', password) and re.search(r'[a-z]', password):
                score += 1
            if re.search(r'\d', password):
                score += 1
            if re.search(r'[!@#$%^&*()\-_=+\[\]{}|;:,.<>?]', password):
                score += 1

            if score >= 3:
                result["strength"] = "strong"
            elif score >= 2:
                result["strength"] = "medium"
            else:
                result["strength"] = "weak"

        return result

    def get_security_headers(self) -> Dict[str, str]:
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }

    def _log_security_alert(self, alert_type: str, data: Dict[str, Any]):
        import logging
        logger = logging.getLogger("security")

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "alert_type": alert_type,
            "data": data,
            "config_version": "1.0"
        }

        logger.warning(f"SECURITY ALERT: {json.dumps(log_entry)}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.config,
            "blocked_attempts": self.get_blocked_attempts()
        }