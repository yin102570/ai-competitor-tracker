"""
全局配置管理 - 基于 pydantic-settings v2
安全规则：所有敏感配置必须从环境变量注入，严禁硬编码
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置，自动从 .env 文件和环境变量加载"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === 应用配置 ===
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_name: str = "ai-competitor-tracker"

    # === 数据库 ===
    database_url: str = "sqlite+aiosqlite:///./data/tracker.db"

    # === Redis ===
    redis_url: str = "redis://localhost:6379/0"
    redis_token_blacklist_db: int = 1

    # === JWT 认证 ===
    jwt_secret_key: str = "CHANGE_ME_TO_RANDOM_256_BIT_KEY"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # === API Key ===
    api_key_prefix: str = "act_"
    api_key_length: int = 32

    # === DeepSeek API ===
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # === 爬虫配置 ===
    spider_concurrency: int = 5
    spider_rate_limit_per_sec: int = 2
    spider_proxy_pool_url: str = ""

    # === 日志 ===
    log_level: str = "INFO"
    log_file: str = "./logs/app.log"

    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.app_env == "development"

    def validate_security(self) -> list[str]:
        """
        安全自检 - 检查关键配置是否安全
        返回警告列表，空列表表示全部通过
        """
        warnings: list[str] = []

        if self.jwt_secret_key == "CHANGE_ME_TO_RANDOM_256_BIT_KEY":
            warnings.append("JWT_SECRET_KEY 仍为默认值，生产环境必须替换")

        if self.is_production and self.app_debug:
            warnings.append("生产环境不应开启 APP_DEBUG")

        if self.is_production and "sqlite" in self.database_url:
            warnings.append("生产环境不应使用 SQLite")

        if not self.deepseek_api_key:
            warnings.append("DEEPSEEK_API_KEY 未配置，AI功能不可用")

        return warnings


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例"""
    return Settings()


settings = get_settings()
