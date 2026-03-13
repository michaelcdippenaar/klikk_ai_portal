"""
Standalone configuration for the TM1 + PostgreSQL MCP Server.
Loads connection settings from environment variables / .env file.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- TM1 Server ---
    tm1_host: str = "192.168.1.194"
    tm1_port: int = 44414
    tm1_user: str = "admin"
    tm1_password: str = ""
    tm1_ssl: bool = False

    # --- PostgreSQL: klikk_financials (Xero GL, investments) ---
    pg_financials_host: str = "192.168.1.235"
    pg_financials_port: int = 5432
    pg_financials_db: str = "klikk_financials_v4"
    pg_financials_user: str = "klikk_user"
    pg_financials_password: str = ""

    # --- PostgreSQL: klikk_bi_etl (BI metrics) ---
    pg_bi_host: str = "192.168.1.235"
    pg_bi_port: int = 5432
    pg_bi_db: str = "klikk_bi_etl"
    pg_bi_user: str = "klikk_user"
    pg_bi_password: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

TM1_CONFIG = {
    "address": settings.tm1_host,
    "port": settings.tm1_port,
    "user": settings.tm1_user,
    "password": settings.tm1_password,
    "ssl": settings.tm1_ssl,
}
