"""
Configuration management for the Code Review Agent using Pydantic.
"""

from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalysisConfig(BaseModel):
    """Configuration for a specific analysis type."""
    enabled: bool = True
    severity: str = "medium"
    max_issues: int = 10

    @field_validator('severity')
    def validate_severity(cls, v):
        if v not in ["low", "medium", "high"]:
            raise ValueError("Severity must be one of: low, medium, high")
        return v


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # OpenAI/OpenRouter Configuration
    # You can provide OPENAI_API_KEY or OPENROUTER_API_KEY
    openai_api_key: str | None = Field(None, description="OpenAI or OpenRouter API key")
    openrouter_api_key: str | None = Field(None, description="OpenRouter API key (alternative)")
    openai_model: str = Field("mistralai/mistral-7b-instruct", description="Model ID (OpenRouter model id by default)")
    openai_base_url: str = Field("https://openrouter.ai/api/v1", description="Base URL for OpenAI-compatible API (OpenRouter by default)")
    
    # Application Settings
    max_file_size_mb: int = Field(10, description="Maximum file size in MB")
    supported_languages: List[str] = Field(
        default_factory=lambda: ["python", "javascript", "typescript", "java", "go"],
        description="List of supported programming languages"
    )
    
    # Analysis Configuration
    analyses: Dict[str, AnalysisConfig] = Field(
        default_factory=lambda: {
            "security": AnalysisConfig(
                enabled=True,
                severity="high",
                max_issues=10
            ),
            "maintainability": AnalysisConfig(
                enabled=True,
                severity="medium",
                max_issues=15
            ),
            "style": AnalysisConfig(
                enabled=True,
                severity="low",
                max_issues=20
            )
        },
        description="Configuration for different analysis types"
    )
    
    # GitHub Integration (optional)
    github_token: Optional[str] = Field(None, description="GitHub API token")
    
    @model_validator(mode='after')
    def validate_settings(self) -> 'Settings':
        """Validate the entire settings object."""
        # Allow either OPENAI_API_KEY or OPENROUTER_API_KEY
        if not self.openai_api_key and self.openrouter_api_key:
            object.__setattr__(self, 'openai_api_key', self.openrouter_api_key)
        if not self.openai_api_key:
            raise ValueError("API key is required. Set OPENAI_API_KEY or OPENROUTER_API_KEY in .env")
        return self


# Create a single instance of settings to be imported
config = Settings()
