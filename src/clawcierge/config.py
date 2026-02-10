from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://clawcierge:clawcierge_dev@localhost:5432/clawcierge_dev"
    )
    app_env: str = "development"
    log_level: str = "info"

    request_expiry_seconds: int = 300
    pipeline_stage_timeout_seconds: int = 5

    ws_heartbeat_interval_seconds: int = 15
    ws_heartbeat_timeout_seconds: int = 60
    ws_max_message_size: int = 65536

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
