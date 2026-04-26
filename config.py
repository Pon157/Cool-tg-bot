from pydantic_settings import BaseSettings
from typing import List, Dict


class Settings(BaseSettings):
    BOT_TOKEN: str
    SOCKS5_PROXY: str = ""

    POSTGRES_DSN: str

    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET_NAME: str = "anon-support"
    S3_PUBLIC_URL: str = ""

    QWEN_API_KEY: str = ""
    QWEN_API_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-plus"

    ADMIN_GROUP_ID: int = 0
    ADMIN_APPLY_TOPIC_ID: int = 0

    # Суперадмины: список Telegram ID
    SUPERADMIN_IDS: List[int] = []
    # Логины и пароли суперадминов в формате "login:password,login2:password2"
    SUPERADMIN_CREDENTIALS: str = ""

    JWT_SECRET: str = "change-me-to-random-string"
    JWT_ALGORITHM: str = "HS256"

    # Базовый URL сайта БЕЗ слеша в конце, напр. https://yourdomain.com
    WEBAPP_URL: str = "https://yourdomain.com"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Стоимость одного сообщения в рублях
    MESSAGE_RATE: float = 0.1

    class Config:
        env_file = ".env"

    def get_superadmin_credentials(self) -> Dict[str, str]:
        """Парсит SUPERADMIN_CREDENTIALS в словарь {login: password}."""
        result: Dict[str, str] = {}
        if not self.SUPERADMIN_CREDENTIALS:
            return result
        for pair in self.SUPERADMIN_CREDENTIALS.split(","):
            pair = pair.strip()
            if ":" in pair:
                login, pwd = pair.split(":", 1)
                result[login.strip()] = pwd.strip()
        return result


settings = Settings()
