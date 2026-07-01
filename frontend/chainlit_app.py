"""
Chainlit chat UI for the multi-agent orchestrator.

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


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("history", [])
    await cl.Message(content=CHAT_GREETING).send()


@cl.on_message
async def on_message(message: cl.Message):
    history: list[dict] = cl.user_session.get("history", [])
    history.append({"role": "user", "content": message.content})

    payload = {
        "input": history,
        "stream": True,
        "context": {"conversation_id": cl.context.session.id},
    }

    response_msg = cl.Message(content="")
    await response_msg.send()
    full_text = ""

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            async with client.stream("POST", BACKEND_URL, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                        # OpenAI Responses API SSE: response.output_text.delta
                        if event.get("type") == "response.output_text.delta":
                            token = event.get("delta", "")
                            if token:
                                await response_msg.stream_token(token)
                                full_text += token
                    except json.JSONDecodeError:
                        pass

    except httpx.ConnectError:
        response_msg.content = (
            f"Cannot connect to backend at `{BACKEND_URL}`. "
            "Ensure the backend is running: `uv run start-server`"
        )
        await response_msg.update()
        return
    except httpx.HTTPStatusError as e:
        response_msg.content = f"Backend returned HTTP {e.response.status_code}."
        await response_msg.update()
        return
    except Exception:
        logger.exception("Unexpected error calling backend")
        response_msg.content = "An unexpected error occurred. Check backend.log for details."
        await response_msg.update()
        return

    await response_msg.update()

    if full_text:
        history.append({"role": "assistant", "content": full_text})
        cl.user_session.set("history", history)
