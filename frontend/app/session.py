"""Session state helpers for Chainlit user interactions."""

from typing import Any, cast

import chainlit as cl

SESSION_HISTORY_KEY = "history"
SESSION_FORWARDED_TOKEN_KEY = "forwarded_access_token"


def init_session() -> None:
    """Initialize user session defaults for a new chat."""
    cl.user_session.set(SESSION_HISTORY_KEY, [])
    cl.user_session.set(SESSION_FORWARDED_TOKEN_KEY, None)


def get_history() -> list[dict[str, Any]]:
    """Return the session conversation history."""
    return cast(list[dict[str, Any]], cl.user_session.get(SESSION_HISTORY_KEY) or [])


def set_history(history: list[dict[str, Any]]) -> None:
    """Persist conversation history in session state."""
    cl.user_session.set(SESSION_HISTORY_KEY, history)


def get_forwarded_token() -> str | None:
    """Return forwarded OBO token if set for this chat session."""
    token = cl.user_session.get(SESSION_FORWARDED_TOKEN_KEY)
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def set_forwarded_token(token: str | None) -> None:
    """Set forwarded OBO token for this chat session."""
    cl.user_session.set(SESSION_FORWARDED_TOKEN_KEY, token)


def token_status_line() -> str:
    """Return a user-facing summary of active authorization mode."""
    if get_forwarded_token():
        return "Auth mode for this chat: Hybrid (app + forwarded user OBO token)."
    return "Auth mode for this chat: App identity only."
