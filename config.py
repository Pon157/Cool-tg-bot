from pydantic_settings import BaseSettings
from typing import List


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
    # ID топика (thread) в ADMIN_GROUP куда приходят заявки на администратора
    ADMIN_APPLY_TOPIC_ID: int = 0
    SUPERADMIN_IDS: List[int] = []

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"

    # Базовый URL сайта (без /webapp), напр. https://yourdomain.com
    WEBAPP_URL: str = "https://sadfsvdb.webtm.ru"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    class Config:
        env_file = ".env"


settings = Settings()
