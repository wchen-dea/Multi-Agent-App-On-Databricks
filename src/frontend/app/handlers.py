"""Chainlit event handlers for chat lifecycle and backend proxy streaming."""

import json
import logging
from typing import Any

import chainlit as cl
import httpx

from frontend.app.commands import mask_token, parse_token_command
from frontend.app.config import get_settings
from frontend.app.session import (
    get_forwarded_token,
    get_history,
    get_persona,
    init_session,
    persona_status_line,
    set_forwarded_token,
    set_history,
    set_persona,
    token_status_line,
)
from frontend.app.stream_events import update_stream_hints
from frontend.app.ui_content import (
    session_status_badge_line,
    source_badge_line,
    starter_prompts,
    welcome_message,
)

logger = logging.getLogger(__name__)
SETTINGS = get_settings()


def _build_payload(history: list[dict[str, Any]], user_message: str) -> dict[str, Any]:
    """Build backend request payload with conversation context."""
    history.append({"role": "user", "content": user_message})
    payload: dict[str, Any] = {
        "input": history,
        "stream": True,
        "context": {"conversation_id": cl.context.session.id},
    }
    persona = get_persona()
    if persona:
        payload["custom_inputs"] = {"persona": persona}
    return payload


def _build_headers() -> dict[str, str]:
    """Build backend request headers including optional forwarded token."""
    headers: dict[str, str] = {}
    token = get_forwarded_token()
    if token:
        headers[SETTINGS.forwarded_access_token_header] = token
    return headers


async def _set_error(message: cl.Message, content: str) -> None:
    """Update an in-flight Chainlit response message with an error."""
    status_line = session_status_badge_line(
        persona=get_persona(),
        token_forwarding_enabled=bool(get_forwarded_token()),
    )
    message.content = f"{content}{status_line}"
    await message.update()


@cl.set_starters
async def set_starters(
    current_user: cl.User | None,
    current_chat_profile: str | None,
) -> list[cl.Starter]:
    """Provide curated starter prompts for faster first interaction."""
    del current_user, current_chat_profile
    return starter_prompts()


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialize chat session state and send welcome panel."""
    init_session()
    await cl.Message(
        content=welcome_message(
            company_name=SETTINGS.company_name,
            company_tagline=SETTINGS.company_tagline,
            chat_greeting=SETTINGS.chat_greeting,
            set_token_command=SETTINGS.set_token_command,
            clear_token_command=SETTINGS.clear_token_command,
            set_persona_command=SETTINGS.set_persona_command,
            clear_persona_command=SETTINGS.clear_persona_command,
            allowed_personas=SETTINGS.allowed_personas,
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Proxy user requests to backend and stream assistant responses."""
    command, token = parse_token_command(
        message.content,
        SETTINGS.set_token_command,
        SETTINGS.clear_token_command,
    )

    from frontend.app.commands import parse_persona_command

    persona_command, persona = parse_persona_command(
        message.content,
        SETTINGS.set_persona_command,
        SETTINGS.clear_persona_command,
    )
    if command == "clear":
        set_forwarded_token(None)
        await cl.Message(
            content=(
                "Forwarded user token removed for this chat session.\n"
                f"{token_status_line()}\n"
                f"{persona_status_line()}"
            )
        ).send()
        return

    if command == "set":
        if not token:
            await cl.Message(
                content=(
                    "Token command format: "
                    f"{SETTINGS.set_token_command} <databricks_access_token>"
                )
            ).send()
            return
        set_forwarded_token(token)
        await cl.Message(
            content=(
                "Forwarded user token saved for this chat session.\n"
                f"Token: `{mask_token(token)}`\n"
                f"Subsequent requests will include {SETTINGS.forwarded_access_token_header}.\n"
                f"{token_status_line()}\n"
                f"{persona_status_line()}"
            )
        ).send()
        return

    if persona_command == "clear":
        set_persona(None)
        await cl.Message(
            content=(
                "Persona cleared for this chat session.\n"
                f"{persona_status_line()}"
            )
        ).send()
        return

    if persona_command == "set":
        if not persona:
            await cl.Message(
                content=(
                    "Persona command format: "
                    f"{SETTINGS.set_persona_command} <persona>\n"
                    f"Accepted personas: {', '.join(SETTINGS.allowed_personas)}"
                )
            ).send()
            return
        normalized_persona = persona.lower()
        if normalized_persona not in set(SETTINGS.allowed_personas):
            await cl.Message(
                content=(
                    f"Invalid persona: `{persona}`.\n"
                    f"Accepted personas: {', '.join(SETTINGS.allowed_personas)}"
                )
            ).send()
            return
        set_persona(normalized_persona)
        await cl.Message(
            content=(
                "Persona saved for this chat session.\n"
                f"{persona_status_line()}"
            )
        ).send()
        return

    history = get_history()
    payload = _build_payload(history, message.content)
    headers = _build_headers()

    response_msg = cl.Message(content="Working on your request...")
    await response_msg.send()

    full_text_parts: list[str] = []
    source_categories: set[str] = set()
    source_tools: set[str] = set()
    streamed_text = False

    try:
        async with httpx.AsyncClient(timeout=SETTINGS.timeout_seconds) as client:
            async with client.stream(
                "POST",
                SETTINGS.backend_url,
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
                    except json.JSONDecodeError:
                        continue

                    delta = update_stream_hints(event, source_categories, source_tools)

                    if delta:
                        streamed_text = True
                        await response_msg.stream_token(delta)
                        full_text_parts.append(delta)

    except httpx.ConnectError:
        await _set_error(
            response_msg,
            (
                f"Cannot connect to backend at `{SETTINGS.backend_url}`. "
                "Ensure the backend is running: `uv run start-server`"
            ),
        )
        return
    except httpx.HTTPStatusError as exc:
        details = (exc.response.text or "").strip()
        suffix = f" Details: {details[:300]}" if details else ""
        await _set_error(
            response_msg,
            f"Backend returned HTTP {exc.response.status_code}.{suffix}",
        )
        return
    except Exception:
        logger.exception("Unexpected error calling backend")
        await _set_error(
            response_msg,
            "An unexpected error occurred. Check backend.log for details.",
        )
        return

    if not streamed_text:
        await _set_error(
            response_msg,
            (
                "The backend ended the stream without returning visible content. "
                "This often means the response was blocked before it could be shown, "
                "for example by an `evidence_required` guardrail."
            ),
        )
        return

    badge_line = source_badge_line(source_categories, source_tools)
    if badge_line:
        await response_msg.stream_token(badge_line)
        full_text_parts.append(badge_line)

    status_line = session_status_badge_line(
        persona=get_persona(),
        token_forwarding_enabled=bool(get_forwarded_token()),
    )
    await response_msg.stream_token(status_line)
    full_text_parts.append(status_line)

    await response_msg.update()

    full_text = "".join(full_text_parts)
    if full_text:
        history.append({"role": "assistant", "content": full_text})
        set_history(history)
