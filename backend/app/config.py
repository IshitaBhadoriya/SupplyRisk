from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    github_token: str = ""
    jwt_secret_key: str = "dev-secret-change-me"

    class Config:
        env_file = ".env"
        # allows DATABASE_URL / REDIS_URL etc. (uppercase) from the environment
        case_sensitive = False


settings = Settings()
