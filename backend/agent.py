"""
Orchestrate multi-agent request routing.

Routes user requests to configured backends via the OpenAI Agents SDK:
    1. Databricks App subagents (DatabricksOpenAI Responses API)
    2. Genie spaces (Databricks MCP server)
    3. Serving endpoints (DatabricksOpenAI Responses API)

Configuration required: edit subagent definitions in `backend/subagent_config.py`,
then update ORCHESTRATOR_MODEL if needed.

Serving endpoints must use task type agent/v1/responses ("Agent (Responses)" in
the Serving UI). Chat Completions endpoints will not work.
"""

import logging
from contextlib import AsyncExitStack
from typing import AsyncGenerator

import mlflow
from agents import Runner, set_default_openai_api, set_default_openai_client
from agents.tracing import set_trace_processors
from databricks_openai import AsyncDatabricksOpenAI
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

from backend.orchestrator import (
    build_mcp_servers,
    build_subagent_tools,
    connect_healthy_mcp_servers,
    create_orchestrator_agent,
)
from backend.request_utils import extract_mcp_errors, to_messages
from backend.subagent_config import SUBAGENTS
from backend.utils import get_session_id, process_agent_stream_events

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ORCHESTRATOR_MODEL = "databricks-gpt-5-2"

# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

# A single client instance is shared and also registered as the Agents SDK default
# to avoid redundant client initialization.
_client = AsyncDatabricksOpenAI()
set_default_openai_client(_client)
set_default_openai_api("chat_completions")
set_trace_processors([])  # only use mlflow for trace processing
mlflow.openai.autolog()
logging.getLogger("mlflow.utils.autologging_utils").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)
if not SUBAGENTS:
    logger.warning(
        "No subagents configured. The orchestrator will run without routing tools."
    )

# ---------------------------------------------------------------------------
# Subagent tools
# ---------------------------------------------------------------------------

subagent_tools = build_subagent_tools(SUBAGENTS, _client)


@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    """Handle a non-streaming agent invocation.

    Args:
        request: Responses API request payload.

    Returns:
        Non-streaming Responses API output payload.
    """
    if session_id := get_session_id(request):
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})
    try:
        async with AsyncExitStack() as stack:
            servers, unavailable = await connect_healthy_mcp_servers(
                stack, build_mcp_servers(SUBAGENTS)
            )
            agent = create_orchestrator_agent(
                ORCHESTRATOR_MODEL,
                SUBAGENTS,
                servers,
                subagent_tools,
                unavailable,
            )
            messages = to_messages(request.input)
            result = await Runner.run(agent, messages)
            return ResponsesAgentResponse(
                output=[item.to_input_item() for item in result.new_items]
            )
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
    """Handle a streaming agent invocation.

    Args:
        request: Responses API request payload.

    Yields:
        Stream events produced by the orchestrator.
    """
    if session_id := get_session_id(request):
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})
    try:
        async with AsyncExitStack() as stack:
            servers, unavailable = await connect_healthy_mcp_servers(
                stack, build_mcp_servers(SUBAGENTS)
            )
            agent = create_orchestrator_agent(
                ORCHESTRATOR_MODEL,
                SUBAGENTS,
                servers,
                subagent_tools,
                unavailable,
            )
            messages = to_messages(request.input)
            result = Runner.run_streamed(agent, input=messages)
            async for event in process_agent_stream_events(result.stream_events()):
                yield event
    except Exception as e:
        mcp_errors = extract_mcp_errors(e)
        if mcp_errors:
            logger.warning(
                "MCP tool error during stream: %s",
                "; ".join(str(x) for x in mcp_errors),
            )
            return
        raise
