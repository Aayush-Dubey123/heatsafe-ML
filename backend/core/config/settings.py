from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
_MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """
    Typed runtime configuration for the HeatSafe-ML backend.

    Values come only from `HEATSAFE_*` environment variables or the root `.env`
    file; no secret or connection string has a default in code.

    Attributes:
        environment (str): Runtime mode: development, test, or production.
        app_version (str): Semantic version reported by the API.
        database_url (str): SQLAlchemy URL; PostgreSQL outside of tests.
        jwt_secret_key (SecretStr | None): HMAC key for admin tokens.
        jwt_algorithm (str): JWT signing algorithm.
        access_token_expire_minutes (int): Admin token lifetime in minutes.
        cors_origins (list[str]): Browser origins allowed to call the API.
        host (str): Interface the ASGI server binds to.
        port (int): Port the ASGI server listens on.
    """

    model_config = SettingsConfigDict(
        env_prefix="HEATSAFE_",
        env_file=_ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    app_version: str = "0.1.0"
    database_url: str = Field(min_length=1)
    jwt_secret_key: SecretStr | None = None
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=1, le=1440)
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        """
        Accept CORS origins as a comma-separated string or a JSON list.

        Lets `.env` files use `HEATSAFE_CORS_ORIGINS=https://a.app,https://b.app`.

        Args:
            value (object): Raw value read from the environment.

        Returns:
            object: List of trimmed origins, or the value unchanged if already a list.
        """
        if isinstance(value, str) and not value.strip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def enforce_environment_rules(self) -> "Settings":
        """
        Reject configurations that are unsafe for the selected environment.

        SQLite is test-only; production additionally requires a strong JWT secret
        and an explicit CORS allow-list without wildcards.

        Returns:
            Settings: The validated settings instance.

        Raises:
            ValueError: If the database URL, secret, or CORS origins violate the rules.
        """
        is_sqlite = self.database_url.startswith("sqlite")
        if is_sqlite and self.environment != "test":
            raise ValueError("SQLite is only allowed when HEATSAFE_ENVIRONMENT=test; use PostgreSQL.")
        if not is_sqlite and not self.database_url.startswith("postgresql"):
            raise ValueError("HEATSAFE_DATABASE_URL must be a PostgreSQL URL (postgresql+psycopg://...).")
        if self.environment == "production":
            secret = self.jwt_secret_key.get_secret_value() if self.jwt_secret_key else ""
            if len(secret) < _MIN_SECRET_LENGTH:
                raise ValueError(
                    f"HEATSAFE_JWT_SECRET_KEY must be set to at least {_MIN_SECRET_LENGTH} characters in production."
                )
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS origin '*' is not allowed in production.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Build and cache the process-wide settings object.

    Fails fast at first use so the app refuses to start with an invalid configuration.

    Returns:
        Settings: Validated, cached configuration.

    Raises:
        pydantic.ValidationError: If a required variable is missing or a rule is violated.
    """
    return Settings()  # type: ignore[call-arg]
