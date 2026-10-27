"""vision2code.backend.app — FastAPI 应用配置。"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从环境变量读取。"""

    app_name: str = "Vision2Code"
    upload_dir: str = "./data/uploads"
    max_upload_size_mb: int = 50

    class Config:
        env_file = ".env"


settings = Settings()
