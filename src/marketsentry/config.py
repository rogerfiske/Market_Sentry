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
        )

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


# Global config instance
config = Config.from_env()
