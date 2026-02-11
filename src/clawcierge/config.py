from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://clawcierge:clawcierge_dev@localhost:5432/clawcierge_dev"
    )

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        # Fly Postgres sets DATABASE_URL with postgres:// or postgresql:// scheme;
        # SQLAlchemy + asyncpg needs the postgresql+asyncpg:// driver prefix.
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]

        # asyncpg uses "ssl" not libpq's "sslmode" — translate it.
        parsed = urlparse(url)
        if parsed.query:
            params = parse_qs(parsed.query)
            sslmode = params.pop("sslmode", [None])[0]
            if sslmode and "ssl" not in params:
                params["ssl"] = [sslmode]
            url = urlunparse(parsed._replace(query=urlencode(params, doseq=True)))

        self.database_url = url
        return self
    app_env: str = "development"
    log_level: str = "info"

    request_expiry_seconds: int = 300
    pipeline_stage_timeout_seconds: int = 5

    ws_heartbeat_interval_seconds: int = 15
    ws_heartbeat_timeout_seconds: int = 60
    ws_max_message_size: int = 65536

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
