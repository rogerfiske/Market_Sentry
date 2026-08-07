"""Configuration management for Market_Sentry."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()


class Config(BaseModel):
    """Application configuration."""

    # Database
    database_path: str = Field(default="db/marketsentry.db")

    # Data directories
    data_raw_dir: str = Field(default="data/raw")
    data_processed_dir: str = Field(default="data/processed")
    data_exports_dir: str = Field(default="data/exports")
    data_imports_dir: str = Field(default="data/imports")

    # Logging
    log_level: str = Field(default="INFO")
    log_file: str = Field(default="logs/marketsentry.log")

    # Redfin search URLs
    redfin_murrieta_url: Optional[str] = Field(default=None)
    redfin_temecula_url: Optional[str] = Field(default=None)

    # Scoring thresholds
    quiet_score_minimum: float = Field(default=7.0)
    quiet_score_target: float = Field(default=8.0)
    vibrancy_score_target_max: float = Field(default=2.5)
    quiet_score_excellent: float = Field(default=9.0)
    vibrancy_score_excellent_max: float = Field(default=2.0)

    # Effective DOM settings
    effective_dom_lookback_days: int = Field(default=365)

    # HowLoud noise enrichment (opt-in, off by default).
    # The API key is deliberately NOT a field on this model. Config
    # objects get printed in logs and tracebacks; a secret stored here
    # would leak. Read it through get_howloud_api_key() instead.
    howloud_enabled: bool = Field(default=False)
    howloud_base_url: str = Field(
        default="https://api.howloud.com"
    )
    howloud_timeout_seconds: int = Field(default=15)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            database_path=os.getenv("DATABASE_PATH", "db/marketsentry.db"),
            data_raw_dir=os.getenv("DATA_RAW_DIR", "data/raw"),
            data_processed_dir=os.getenv("DATA_PROCESSED_DIR", "data/processed"),
            data_exports_dir=os.getenv("DATA_EXPORTS_DIR", "data/exports"),
            data_imports_dir=os.getenv("DATA_IMPORTS_DIR", "data/imports"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE", "logs/marketsentry.log"),
            redfin_murrieta_url=os.getenv("REDFIN_MURRIETA_URL"),
            redfin_temecula_url=os.getenv("REDFIN_TEMECULA_URL"),
            quiet_score_minimum=float(os.getenv("QUIET_SCORE_MINIMUM", "7.0")),
            quiet_score_target=float(os.getenv("QUIET_SCORE_TARGET", "8.0")),
            vibrancy_score_target_max=float(os.getenv("VIBRANCY_SCORE_TARGET_MAX", "2.5")),
            quiet_score_excellent=float(os.getenv("QUIET_SCORE_EXCELLENT", "9.0")),
            vibrancy_score_excellent_max=float(
                os.getenv("VIBRANCY_SCORE_EXCELLENT_MAX", "2.0")
            ),
            effective_dom_lookback_days=int(os.getenv("EFFECTIVE_DOM_LOOKBACK_DAYS", "365")),
            howloud_enabled=(
                os.getenv("MARKETSENTRY_HOWLOUD_ENABLED", "false")
                .strip()
                .lower()
                in ("1", "true", "yes", "on")
            ),
            howloud_base_url=os.getenv(
                "MARKETSENTRY_HOWLOUD_BASE_URL",
                "https://api.howloud.com",
            ),
            howloud_timeout_seconds=int(
                os.getenv(
                    "MARKETSENTRY_HOWLOUD_TIMEOUT_SECONDS", "15"
                )
            ),
        )

    @property
    def export_path(self) -> str:
        """Alias for data_exports_dir for backward compatibility."""
        return self.data_exports_dir

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        dirs = [
            self.data_raw_dir,
            self.data_processed_dir,
            self.data_exports_dir,
            self.data_imports_dir,
            Path(self.database_path).parent,
            Path(self.log_file).parent,
        ]
        for directory in dirs:
            Path(directory).mkdir(parents=True, exist_ok=True)


HOWLOUD_API_KEY_ENV_VAR = "MARKETSENTRY_HOWLOUD_API_KEY"


def get_howloud_api_key() -> Optional[str]:
    """Read the HowLoud API key from the environment.

    Kept out of the Config model on purpose: config objects are printed
    in logs and tracebacks, and a secret stored as a field would leak
    through them. Callers must pass the return value straight into a
    request header and never store, log, or report it.

    Returns:
        The API key, or None when it is not configured.
    """
    value = os.getenv(HOWLOUD_API_KEY_ENV_VAR, "").strip()
    return value or None


def mask_secret(value: Optional[str]) -> str:
    """Mask a secret for display.

    Shows only the last four characters so an operator can tell which
    key is loaded without the value being readable. Short values are
    fully masked rather than partially revealed.

    Args:
        value: The secret to mask.

    Returns:
        A display-safe string. Never the raw secret.
    """
    if not value:
        return "not set"
    if len(value) <= 8:
        return "*" * 8
    return f"{'*' * 8}{value[-4:]}"


# Global config instance
config = Config.from_env()
