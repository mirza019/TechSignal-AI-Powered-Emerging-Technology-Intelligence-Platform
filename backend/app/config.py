from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    database_url: str = "sqlite:///./radar.db"
    app_secret: str = "local-demo-only-change-this-before-deploying"
    environment: str = "development"
    demo_mode: bool = True
    seed_demo: bool = True
    public_demo: bool = False
    bootstrap_live_catalog: bool = False
    sqlite_backup_path: str = ""
    demo_admin_password: str = "RadarDemo2026!"
    demo_analyst_password: str = "RadarDemo2026!"
    demo_viewer_password: str = "RadarDemo2026!"
    entra_tenant_id: str = ""
    entra_client_id: str = ""
    entra_client_secret: str = ""
    entra_redirect_uri: str = "http://127.0.0.1:5173/api/auth/sso/callback"
    entra_allowed_domains: list[str] = []
    frontend_url: str = "http://127.0.0.1:5173"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    openalex_api_key: str = ""
    semantic_scholar_api_key: str = ""
    epo_consumer_key: str = ""
    epo_consumer_secret: str = ""
    enable_gdelt: bool = True
    enable_semantic_scholar: bool = False
    enable_epo: bool = False
    enable_web_scraping: bool = False
    enable_scheduler: bool = False
    embedding_backend: str = "local"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]
    scraper_allowed_domains: list[str] = []
    scraper_user_agent: str = "TechSignal/1.0 (public research)"
    scraper_interval: float = 2.0

    @model_validator(mode="after")
    def secure_production(self):
        import re

        if self.entra_tenant_id and not re.fullmatch(r"[0-9a-fA-F-]{36}", self.entra_tenant_id):
            raise ValueError("Entra tenant ID must be a specific tenant UUID, not common or organizations")
        if self.environment == "production":
            if not self.frontend_url.startswith("https://") or not self.entra_redirect_uri.startswith("https://"):
                raise ValueError("Production frontend and SSO redirect URLs must use HTTPS")
            if len(self.app_secret) < 32 or self.app_secret.startswith("local-demo"):
                raise ValueError("Production requires a unique APP_SECRET of at least 32 characters")
            if self.seed_demo or self.demo_mode:
                raise ValueError("Production requires SEED_DEMO=false and DEMO_MODE=false")
            if "*" in self.cors_origins:
                raise ValueError("Production CORS must use explicit origins")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
