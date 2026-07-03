"""
Run the Chainlit chat UI for the multi-agent orchestrator.

Connects to the backend MLflow AgentServer at API_PROXY and streams responses
using the OpenAI Responses API SSE format.

Environment variables (loaded from .env):
  API_PROXY                   Backend /invocations URL (set by start-app)
  CHAT_GREETING               Greeting shown on empty chat (optional)
  CHAT_PROXY_TIMEOUT_SECONDS  Request timeout in seconds (default: 300)
"""

import json
import logging
import os
from pathlib import Path

import chainlit as cl
import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

logger = logging.getLogger(__name__)

BACKEND_URL = os.environ.get("API_PROXY", "http://localhost:8000/invocations")
CHAT_GREETING = os.environ.get("CHAT_GREETING", "What would you like to know?")
TIMEOUT = int(os.environ.get("CHAT_PROXY_TIMEOUT_SECONDS", "300"))
FORWARDED_ACCESS_TOKEN_HEADER = "x-forwarded-access-token"
SET_TOKEN_COMMAND = "/token"
CLEAR_TOKEN_COMMAND = "/clear-token"


def _build_payload(history: list[dict], user_message: str) -> dict:
    """Build the backend request payload.

    Args:
        history: In-memory conversation history.
        user_message: Latest user message content.

    Returns:
        Request payload for the backend /invocations endpoint.
    """
    history.append({"role": "user", "content": user_message})
    return {
        "input": history,
        "stream": True,
        "context": {"conversation_id": cl.context.session.id},
    }


def _build_headers() -> dict[str, str]:
    """Build request headers for backend calls.

    Returns:
        Header dictionary including forwarded user token when set.
    """
    headers: dict[str, str] = {}
    token = cl.user_session.get("forwarded_access_token")
    if isinstance(token, str) and token.strip():
        headers[FORWARDED_ACCESS_TOKEN_HEADER] = token.strip()
    return headers


def _parse_token_command(text: str) -> tuple[str | None, str | None]:
    """Parse token management commands from user input.

    Args:
        text: Raw user message content.

    Returns:
        Tuple of (command, token).
        command is one of: "set", "clear", or None.
    """
    stripped = text.strip()
    if stripped == CLEAR_TOKEN_COMMAND:
        return ("clear", None)
    if not stripped.startswith(f"{SET_TOKEN_COMMAND} "):
        return (None, None)
    token = stripped[len(SET_TOKEN_COMMAND) :].strip()
    return ("set", token)


def _extract_delta(event: dict) -> str:
    """Extract a text token from a streamed Responses API event.

    Args:
        event: Parsed SSE event payload.

    Returns:
        Delta token text when present; otherwise an empty string.
    """
    if event.get("type") != "response.output_text.delta":
        return ""
    return event.get("delta", "") or ""


async def _set_error(message: cl.Message, content: str) -> None:
    """Update the Chainlit message with an error response.

    Args:
        message: Chainlit message handle to update.
        content: Error text shown to the user.
    """
    message.content = content
    await message.update()


@cl.on_chat_start
async def on_chat_start():
    """Initialize chat state and send the greeting message."""
    cl.user_session.set("history", [])
    cl.user_session.set("forwarded_access_token", None)
    await cl.Message(
        content=(
            f"{CHAT_GREETING}\n\n"
            "Optional OBO token commands:\n"
            "- /token <databricks_access_token>\n"
            "- /clear-token"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    """Proxy a user message to the backend and stream assistant tokens.

    Args:
        message: Incoming user message event from Chainlit.
    """
    command, token = _parse_token_command(message.content)
    if command == "clear":
        cl.user_session.set("forwarded_access_token", None)
        await cl.Message(content="Cleared forwarded user token for this chat session.").send()
        return
    if command == "set":
        if not token:
            await cl.Message(
                content="Token command format: /token <databricks_access_token>"
            ).send()
            return
        cl.user_session.set("forwarded_access_token", token)
        await cl.Message(
            content=(
                "Forwarded user token saved for this chat session. "
                "Subsequent requests will include x-forwarded-access-token."
            )
        ).send()
        return

    history: list[dict] = cl.user_session.get("history", [])
    payload = _build_payload(history, message.content)
    headers = _build_headers()

    response_msg = cl.Message(content="")
    await response_msg.send()
    full_text = ""

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            async with client.stream(
                "POST",
                BACKEND_URL,
                json=payload,
                headers=headers,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                        # Stream assistant token deltas from Responses API events.
                        token = _extract_delta(event)
                        if token:
                            await response_msg.stream_token(token)
                            full_text += token
                    except json.JSONDecodeError:
                        continue

    except httpx.ConnectError:
        await _set_error(
            response_msg,
            (
                f"Cannot connect to backend at `{BACKEND_URL}`. "
                "Ensure the backend is running: `uv run start-server`"
            ),
        )
        return
    except httpx.HTTPStatusError as e:
        await _set_error(response_msg, f"Backend returned HTTP {e.response.status_code}.")
        return
    except Exception:
        logger.exception("Unexpected error calling backend")
        await _set_error(
            response_msg,
            "An unexpected error occurred. Check backend.log for details.",
        )
        return

    await response_msg.update()

    if full_text:
        history.append({"role": "assistant", "content": full_text})
        cl.user_session.set("history", history)
