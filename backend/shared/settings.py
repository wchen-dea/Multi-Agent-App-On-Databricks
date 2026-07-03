"""Runtime settings for backend services."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AppSettings:
    """Typed runtime settings loaded from environment."""

    orchestrator_model: str = "databricks-gpt-5-2"
    log_level: str = "INFO"
    log_format: str = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    log_date_format: str = "%Y-%m-%d %H:%M:%S"


def get_settings() -> AppSettings:
    """Load backend runtime settings from environment variables."""
    return AppSettings(
        orchestrator_model=os.getenv("ORCHESTRATOR_MODEL", "databricks-gpt-5-2"),
        log_level=os.getenv("BACKEND_LOG_LEVEL", "INFO"),
        log_format=os.getenv(
            "BACKEND_LOG_FORMAT",
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
        ),
        log_date_format=os.getenv("BACKEND_LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S"),
    )
