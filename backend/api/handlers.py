"""Orchestrate multi-agent request routing handlers."""

import logging
from contextlib import AsyncExitStack
from typing import Any, AsyncGenerator, cast

import mlflow
from agents import Runner, set_default_openai_api, set_default_openai_client
from agents.exceptions import UserError
from agents.tracing import set_trace_processors
from databricks_openai import AsyncDatabricksOpenAI
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

from backend.api.dependencies import get_handler_dependencies
from backend.domain.subagent_config import SUBAGENTS
from backend.shared.request_utils import extract_mcp_errors, to_messages
from backend.shared.settings import get_settings
from backend.shared.runtime_utils import process_agent_stream_events

SETTINGS = get_settings()
HANDLER_DEPS = get_handler_dependencies()

_client = AsyncDatabricksOpenAI()
set_default_openai_client(_client)
set_default_openai_api("chat_completions")
set_trace_processors([])
cast(Any, mlflow).openai.autolog()
logger = logging.getLogger(__name__)
if not SUBAGENTS:
    logger.warning("No subagents configured. The orchestrator will run without routing tools.")


def _response_text_from_items(items: list[Any]) -> str:
    """Extract plain text from output items for guardrail evaluation."""
    chunks: list[str] = []
    for item in items:
        data = item.to_input_item() if hasattr(item, "to_input_item") else item
        if not isinstance(data, dict):
            continue
        content = data.get("content")
        if isinstance(content, str):
            chunks.append(content)
            continue
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text")
                    if isinstance(text, str) and text.strip():
                        chunks.append(text)
    return "\n".join(chunks).strip()


def _text_from_stream_event(event: Any) -> str:
    """Extract text fragments from normalized stream events."""
    data = event.model_dump() if hasattr(event, "model_dump") else event
    if not isinstance(data, dict):
        return ""

    if data.get("type") == "response.output_text.delta":
        delta = data.get("delta")
        return delta if isinstance(delta, str) else ""

    item = data.get("item")
    if isinstance(item, dict):
        content = item.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            ]
            return " ".join(chunks)
    return ""


@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    HANDLER_DEPS.message_bus.publish(
        "request.invoke.started",
        {
            "subagents_total": len(SUBAGENTS),
        },
    )
    runtime_auth = HANDLER_DEPS.runtime_auth_builder(request, SUBAGENTS, _client)

    try:
        async with AsyncExitStack() as stack:
            servers, unavailable_health = await HANDLER_DEPS.mcp_connector(
                stack, runtime_auth.mcp_servers
            )
            unavailable = runtime_auth.unavailable_auth + unavailable_health
            agent = HANDLER_DEPS.orchestrator_factory(
                SETTINGS.orchestrator_model,
                SUBAGENTS,
                servers,
                runtime_auth.subagent_tools,
                unavailable,
            )
            messages = to_messages(request.input)
            result = await Runner.run(agent, messages)
            response_text = _response_text_from_items(result.new_items)
            guardrail = HANDLER_DEPS.guardrails_evaluator(
                response_text,
                runtime_auth.policy_allowed_subagents,
            )
            if guardrail.blocked:
                HANDLER_DEPS.message_bus.publish(
                    "response.guardrail.blocked",
                    {
                        "reasons": list(guardrail.reasons),
                    },
                )
                raise UserError(
                    "Response blocked by guardrails: " + ", ".join(guardrail.reasons)
                )
            HANDLER_DEPS.message_bus.publish(
                "response.guardrail.passed",
                {
                    "reasons": list(guardrail.reasons),
                },
            )
            HANDLER_DEPS.message_bus.publish(
                "request.invoke.succeeded",
                {
                    "output_items": len(result.new_items),
                    "unavailable_tools": len(unavailable),
                },
            )
            return ResponsesAgentResponse(
                output=cast(Any, [item.to_input_item() for item in result.new_items])
            )
    except UserError as e:
        HANDLER_DEPS.message_bus.publish(
            "request.invoke.failed",
            {
                "error_type": type(e).__name__,
                "reason": "authorization",
            },
        )
        logger.warning("Authorization error during invoke: %s", e)
        raise
    except Exception as e:
        HANDLER_DEPS.message_bus.publish(
            "request.invoke.failed",
            {
                "error_type": type(e).__name__,
            },
        )
        mcp_errors = extract_mcp_errors(e)
        if mcp_errors:
            logger.warning(
                "MCP tool error during invoke: %s",
                "; ".join(str(x) for x in mcp_errors),
            )
        raise


@stream()
async def stream_handler(
    request: ResponsesAgentRequest,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    HANDLER_DEPS.message_bus.publish(
        "request.stream.started",
        {
            "subagents_total": len(SUBAGENTS),
        },
    )
    runtime_auth = HANDLER_DEPS.runtime_auth_builder(request, SUBAGENTS, _client)

    try:
        async with AsyncExitStack() as stack:
            servers, unavailable_health = await HANDLER_DEPS.mcp_connector(
                stack, runtime_auth.mcp_servers
            )
            unavailable = runtime_auth.unavailable_auth + unavailable_health
            agent = HANDLER_DEPS.orchestrator_factory(
                SETTINGS.orchestrator_model,
                SUBAGENTS,
                servers,
                runtime_auth.subagent_tools,
                unavailable,
            )
            messages = to_messages(request.input)
            result = Runner.run_streamed(agent, input=messages)
            event_count = 0
            buffered_events: list[Any] = []
            streamed_text_parts: list[str] = []
            async for event in process_agent_stream_events(result.stream_events()):
                event_count += 1
                buffered_events.append(event)
                text = _text_from_stream_event(event)
                if text:
                    streamed_text_parts.append(text)

            guardrail = HANDLER_DEPS.guardrails_evaluator(
                "\n".join(streamed_text_parts),
                runtime_auth.policy_allowed_subagents,
            )
            if guardrail.blocked:
                HANDLER_DEPS.message_bus.publish(
                    "response.guardrail.blocked",
                    {
                        "reasons": list(guardrail.reasons),
                        "mode": "stream",
                    },
                )
                raise UserError(
                    "Response blocked by guardrails: " + ", ".join(guardrail.reasons)
                )

            HANDLER_DEPS.message_bus.publish(
                "response.guardrail.passed",
                {
                    "reasons": list(guardrail.reasons),
                    "mode": "stream",
                },
            )
            for event in buffered_events:
                yield event
            HANDLER_DEPS.message_bus.publish(
                "request.stream.succeeded",
                {
                    "events_streamed": event_count,
                    "unavailable_tools": len(unavailable),
                },
            )
    except UserError as e:
        HANDLER_DEPS.message_bus.publish(
            "request.stream.failed",
            {
                "error_type": type(e).__name__,
                "reason": "authorization",
            },
        )
        logger.warning("Authorization error during stream: %s", e)
        raise
    except Exception as e:
        HANDLER_DEPS.message_bus.publish(
            "request.stream.failed",
            {
                "error_type": type(e).__name__,
            },
        )
        mcp_errors = extract_mcp_errors(e)
        if mcp_errors:
            logger.warning(
                "MCP tool error during stream: %s",
                "; ".join(str(x) for x in mcp_errors),
            )
            return
        raise
