"""
Central configuration for the Klikk Planning Agent.
All settings are loaded from agent/.env via pydantic-settings.
Supports both Anthropic (Claude) and OpenAI (GPT) as AI providers.
"""
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- AI Provider toggle ---
    ai_provider: str = "openai"  # "anthropic" or "openai"

    # --- Anthropic ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # --- OpenAI ---
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # --- Shared AI settings ---
    max_tokens: int = 4096
    max_tool_rounds: int = 10

    # --- VoyageAI embeddings ---
    voyage_api_key: str = ""
    voyage_model: str = "voyage-3-lite"
    embedding_dim: int = 512  # voyage-3-lite output dimension

    # --- TM1 Server ---
    tm1_host: str = "192.168.1.194"
    tm1_port: int = 44414
    tm1_user: str = "admin"
    tm1_password: str = ""
    tm1_ssl: bool = False

    # --- PostgreSQL: klikk_financials_v4 ---
    pg_financials_host: str = "192.168.1.235"
    pg_financials_port: int = 5432
    pg_financials_db: str = "klikk_financials_v4"
    pg_financials_user: str = "klikk_user"
    pg_financials_password: str = ""

    # --- PostgreSQL: klikk_bi_etl (also hosts RAG vectors) ---
    pg_bi_host: str = "192.168.1.235"
    pg_bi_port: int = 5432
    pg_bi_db: str = "klikk_bi_etl"
    pg_bi_user: str = "klikk_user"
    pg_bi_password: str = ""

    # --- RAG ---
    rag_schema: str = "agent_rag"
    rag_top_k: int = 5
    rag_min_score: float = 0.60

    # --- Web Search ---
    web_search_enabled: bool = True
    web_search_provider: str = "duckduckgo"
    web_search_api_key: str = ""
    web_search_max_results: int = 5

    # --- Google Drive ---
    google_drive_enabled: bool = False
    google_drive_credentials_path: str = ""
    google_drive_folder_ids: str = ""  # comma-separated folder IDs

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

# Convenience dict for TM1py TM1Service constructor
TM1_CONFIG = {
    "address": settings.tm1_host,
    "port": settings.tm1_port,
    "user": settings.tm1_user,
    "password": settings.tm1_password,
    "ssl": settings.tm1_ssl,
}
