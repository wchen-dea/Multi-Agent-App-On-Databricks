"""Configuration and environment loading for frontend chat UI."""

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent.parent / ".env", override=True)


@dataclass(frozen=True)
class FrontendSettings:
    """Typed runtime settings for the Chainlit frontend."""

    backend_url: str
    chat_greeting: str
    timeout_seconds: int
    company_name: str
    company_tagline: str
    forwarded_access_token_header: str = "x-forwarded-access-token"
    set_token_command: str = "/token"
    clear_token_command: str = "/clear-token"


@lru_cache(maxsize=1)
def get_settings() -> FrontendSettings:
    """Load frontend settings from environment variables."""
    return FrontendSettings(
        backend_url=os.environ.get("API_PROXY", "http://localhost:8000/invocations"),
        chat_greeting=os.environ.get("CHAT_GREETING", "What would you like to know?"),
        timeout_seconds=int(os.environ.get("CHAT_PROXY_TIMEOUT_SECONDS", "300")),
        company_name=os.environ.get("CHAT_COMPANY_NAME", "Databricks"),
        company_tagline=os.environ.get("CHAT_COMPANY_TAGLINE", "Enterprise AI Assistant"),
    )
