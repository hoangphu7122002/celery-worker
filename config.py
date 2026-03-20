import os

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(".env", override=False) or load_dotenv(".env.dev", override=False)
if environment := os.getenv("ENVIRONMENT", "").lower():
    load_dotenv(f".env.{environment}", override=True)


class DatabaseSettings(BaseModel):
    url: str


class RedisSettings(BaseModel):
    url: str


class OpenAISettings(BaseModel):
    api_key: str | None = None
    base_url: str | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    database_url: str = "postgresql://postgres:postgres@localhost:5432/cursor_worker"
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    conversation_model: str = "gpt-4o-mini"
    zendesk_webhook_enabled: bool = True
    zendesk_subdomain: str = ""
    zendesk_email: str = ""
    zendesk_api_token: str = ""
    zendesk_llm_limit_enabled: bool = False
    zendesk_llm_limit_tickets_per_run: int = 5
    zendesk_llm_limit_ttl_seconds: int = 600
    ngrok_domain: str = ""
    environment: str | None = None

    @property
    def database(self) -> DatabaseSettings:
        return DatabaseSettings(url=self.database_url)

    @property
    def redis(self) -> RedisSettings:
        return RedisSettings(url=self.redis_url)

    @property
    def openai(self) -> OpenAISettings:
        return OpenAISettings(api_key=self.openai_api_key, base_url=self.openai_base_url)


settings = Settings()
