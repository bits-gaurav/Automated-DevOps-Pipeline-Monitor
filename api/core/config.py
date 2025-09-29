from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    """Application settings"""
    
    # GitHub API settings
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_OWNER: str = os.getenv("GITHUB_OWNER", "")
    GITHUB_REPO: str = os.getenv("GITHUB_REPO", "")
    
    # Slack settings
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    SLACK_ANALYTICS_WEBHOOK_URL: str = os.getenv("SLACK_ANALYTICS_WEBHOOK_URL", "")
    
    # Container registry settings
    REGISTRY: str = os.getenv("REGISTRY", "ghcr.io")
    
    # API settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "DevOps Pipeline Monitor API"
    
    # CORS settings
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:4200",
        "http://localhost:8080",
        "https://localhost:3000",
        "https://localhost:4200",
        "https://localhost:8080",
    ]
    
    # Cache settings
    CACHE_TTL: int = 300  # 5 minutes
    
    # Pagination settings
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Analytics settings
    DEFAULT_LOOKBACK_MINUTES: int = 1440  # 24 hours
    MAX_LOOKBACK_MINUTES: int = 10080  # 7 days
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Global settings instance
settings = Settings()
