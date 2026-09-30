from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。环境变量可覆盖（如 DATABASE_URL）。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "机柜物料管理平台"
    # 开发默认连 localhost:5432（docker compose 里 db 服务映射的端口）。
    database_url: str = "postgresql+psycopg://mvp:mvp@localhost:5432/mvp"
    secret_key: str = "dev-secret-change-me"
    # 阶段1固定单部门，不做多租户。
    dept_id: int = 1
    access_token_expire_minutes: int = 60 * 24


settings = Settings()
