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


@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
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
            return ResponsesAgentResponse(
                output=cast(Any, [item.to_input_item() for item in result.new_items])
            )
    except UserError as e:
        logger.warning("Authorization error during invoke: %s", e)
        raise
    except Exception as e:
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
            async for event in process_agent_stream_events(result.stream_events()):
                yield event
    except UserError as e:
        logger.warning("Authorization error during stream: %s", e)
        raise
    except Exception as e:
        mcp_errors = extract_mcp_errors(e)
        if mcp_errors:
            logger.warning(
                "MCP tool error during stream: %s",
                "; ".join(str(x) for x in mcp_errors),
            )
            return
        raise
