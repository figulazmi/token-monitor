from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://tokenuser:tokenpass123@token-db:5432/tokenmonitor"
    app_env: str = "production"

    class Config:
        env_file = ".env"


settings = Settings()
