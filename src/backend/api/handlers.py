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
from backend.domain.subagent_config import SUBAGENTS, SubagentConfig
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


def _guardrail_block_message(reasons: tuple[str, ...]) -> str:
    """Format a safe, user-facing explanation for blocked responses."""
    reason_list = ", ".join(reasons) if reasons else "policy_check_failed"
    return (
        "I couldn't return the answer because the response was blocked by a guardrail "
        f"({reason_list}). For `evidence_required`, ask the agent to include a citation "
        "such as `[1]` or an explicit `Source:` line."
    )


def _candidate_tool_names(data: dict[str, Any]) -> list[str]:
    """Extract candidate tool or subagent names from event or output-item data."""
    candidates: list[str] = []
    for key in ("name", "tool_name"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())

    item = data.get("item")
    if isinstance(item, dict):
        for key in ("name", "tool_name"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())

    return candidates


def _resolve_subagent(candidate: str, subagents: list[SubagentConfig]) -> SubagentConfig | None:
    """Map a streamed tool identifier back to a configured subagent."""
    normalized = candidate.strip()
    if normalized.startswith("query_"):
        normalized = normalized[len("query_") :]
    elif normalized.startswith("Genie:"):
        normalized = normalized.split(":", 1)[1]
    elif normalized.startswith("MCP:"):
        normalized = normalized.split(":", 1)[1]

    for subagent in subagents:
        if normalized in {subagent.name, subagent.tool_name}:
            return subagent
    return None


def _used_subagents_from_payloads(
    payloads: list[dict[str, Any]],
    subagents: list[SubagentConfig],
) -> list[SubagentConfig]:
    """Collect the distinct configured subagents referenced in events or output items."""
    ordered: list[SubagentConfig] = []
    seen: set[str] = set()

    for payload in payloads:
        for candidate in _candidate_tool_names(payload):
            subagent = _resolve_subagent(candidate, subagents)
            if subagent is None or subagent.name in seen:
                continue
            seen.add(subagent.name)
            ordered.append(subagent)

    return ordered


def _governed_source_suffix(used_subagents: list[SubagentConfig]) -> str:
    """Build a deterministic source footer for governed tool-backed answers."""
    governed = [subagent for subagent in used_subagents if subagent.requires_evidence]
    if not governed:
        return ""

    parts: list[str] = []
    for subagent in governed:
        tool_type = "Genie MCP" if subagent.is_genie else subagent.kind.replace("_", " ")
        freshness = subagent.freshness_sla or "unknown freshness"
        parts.append(f"{subagent.name} ({tool_type}, freshness {freshness})")

    return "\n\nSource: " + "; ".join(parts)


def _event_has_tool_activity(payloads: list[dict[str, Any]]) -> bool:
    """Return true when stream/output payloads show any tool execution activity."""
    for payload in payloads:
        event_type = payload.get("type")
        if isinstance(event_type, str) and (
            event_type.startswith("response.output_item")
            or "tool" in event_type
            or "mcp" in event_type
        ):
            item = payload.get("item")
            if isinstance(item, dict):
                item_type = item.get("type")
                if isinstance(item_type, str) and ("tool" in item_type or "mcp" in item_type):
                    return True
            elif "tool" in event_type or "mcp" in event_type:
                return True

        item = payload.get("item")
        if isinstance(item, dict):
            item_type = item.get("type")
            if isinstance(item_type, str) and ("tool" in item_type or "mcp" in item_type):
                return True

    return False


def _governed_source_suffix_with_fallback(
    payloads: list[dict[str, Any]],
    subagents: list[SubagentConfig],
) -> str:
    """Build a governed source suffix with a fallback for unlabelled tool events."""
    used_subagents = _used_subagents_from_payloads(payloads, subagents)
    suffix = _governed_source_suffix(used_subagents)
    if suffix:
        return suffix

    governed = [subagent for subagent in subagents if subagent.requires_evidence]
    if governed and _event_has_tool_activity(payloads):
        return "\n\nSource: tool-backed governed response."

    return ""


def _guardrail_scope_subagents(
    payloads: list[dict[str, Any]],
    subagents: list[SubagentConfig],
) -> list[SubagentConfig]:
    """Limit guardrail checks to subagents that likely contributed to the answer."""
    used_subagents = _used_subagents_from_payloads(payloads, subagents)
    if used_subagents:
        return used_subagents

    if _event_has_tool_activity(payloads):
        return [subagent for subagent in subagents if subagent.requires_evidence]

    return []


def _append_source_to_output_items(
    output_items: list[dict[str, Any]],
    source_suffix: str,
) -> list[dict[str, Any]]:
    """Append a source footer to the last assistant message item."""
    if not source_suffix:
        return output_items

    updated = [dict(item) for item in output_items]
    for item in reversed(updated):
        if item.get("role") != "assistant":
            continue

        content = item.get("content")
        if isinstance(content, str):
            item["content"] = content + source_suffix
            return updated

        if isinstance(content, list):
            mutable_blocks: list[Any] = []
            appended = False
            for block in content:
                if isinstance(block, dict):
                    mutable_blocks.append(dict(block))
                else:
                    mutable_blocks.append(block)
            for block in reversed(mutable_blocks):
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    block["text"] = block["text"] + source_suffix
                    appended = True
                    break
            if not appended:
                mutable_blocks.append({"type": "output_text", "text": source_suffix.strip()})
            item["content"] = mutable_blocks
            return updated

    return output_items


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
            output_items = cast(Any, [item.to_input_item() for item in result.new_items])
            guardrail_subagents = _guardrail_scope_subagents(
                output_items,
                runtime_auth.policy_allowed_subagents,
            )
            source_suffix = _governed_source_suffix_with_fallback(
                output_items,
                guardrail_subagents,
            )
            if source_suffix and source_suffix not in response_text:
                response_text += source_suffix
                output_items = _append_source_to_output_items(output_items, source_suffix)
            guardrail = HANDLER_DEPS.guardrails_evaluator(
                response_text,
                guardrail_subagents,
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
                    "unavailable_tool_details": unavailable,
                },
            )
            return ResponsesAgentResponse(output=cast(Any, output_items))
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

            buffered_payloads = [event for event in buffered_events if isinstance(event, dict)]
            guardrail_subagents = _guardrail_scope_subagents(
                buffered_payloads,
                runtime_auth.policy_allowed_subagents,
            )
            source_suffix = _governed_source_suffix_with_fallback(
                buffered_payloads,
                guardrail_subagents,
            )
            if source_suffix and source_suffix not in "\n".join(streamed_text_parts):
                streamed_text_parts.append(source_suffix)

            guardrail = HANDLER_DEPS.guardrails_evaluator(
                "\n".join(streamed_text_parts),
                guardrail_subagents,
            )
            if guardrail.blocked:
                HANDLER_DEPS.message_bus.publish(
                    "response.guardrail.blocked",
                    {
                        "reasons": list(guardrail.reasons),
                        "mode": "stream",
                    },
                )
                yield ResponsesAgentStreamEvent(
                    type="response.output_text.delta",
                    item_id="item_guardrail",
                    delta=_guardrail_block_message(guardrail.reasons),
                )
                HANDLER_DEPS.message_bus.publish(
                    "request.stream.failed",
                    {
                        "error_type": "UserError",
                        "reason": "guardrail",
                    },
                )
                return

            HANDLER_DEPS.message_bus.publish(
                "response.guardrail.passed",
                {
                    "reasons": list(guardrail.reasons),
                    "mode": "stream",
                },
            )
            for event in buffered_events:
                yield event
            if source_suffix:
                yield ResponsesAgentStreamEvent(
                    type="response.output_text.delta",
                    item_id="item_source",
                    delta=source_suffix,
                )
            HANDLER_DEPS.message_bus.publish(
                "request.stream.succeeded",
                {
                    "events_streamed": event_count,
                    "unavailable_tools": len(unavailable),
                    "unavailable_tool_details": unavailable,
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
