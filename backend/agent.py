"""
Multi-agent orchestrator.

Routes user requests to one or more configured backends via the OpenAI Agents SDK:
  1. Another agent deployed as a Databricks App  (via DatabricksOpenAI Responses API)
  2. A Genie space                                (via built-in Databricks MCP server)
  3. A knowledge-assistant serving endpoint        (via DatabricksOpenAI Responses API)
  4. A model on a serving endpoint                 (via DatabricksOpenAI Responses API)

Configuration required: edit SUBAGENTS below, then update the orchestrator
instructions and model in create_orchestrator_agent().

Serving endpoints must use task type agent/v1/responses ("Agent (Responses)" in
the Serving UI). Chat Completions endpoints will not work.
"""

import logging
from contextlib import AsyncExitStack
from typing import Any, AsyncGenerator

import mlflow
from agents import (
    Agent,
    Runner,
    function_tool,
    set_default_openai_api,
    set_default_openai_client,
)
from agents.exceptions import UserError
from agents.tracing import set_trace_processors
from databricks_openai import AsyncDatabricksOpenAI
from databricks_openai.agents import McpServer
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

from backend.utils import (
    build_mcp_url,
    get_session_id,
    process_agent_stream_events,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ORCHESTRATOR_MODEL = "databricks-gpt-5-2"



SUBAGENTS: list[dict[str, Any]] = [
    {
        "name": "sales_agent",
        "type": "genie",
        "space_id": "01f159f5d91419549020e3609add391c",  # UUID from the Genie space URL
        "description": (
            "Sales agent backed by a Genie space for structured data analysis. "
            "Use this for sales metrics, store performance, and operational reporting."
        ),
    },
    {
        "name": "knowledge_assistant",
        "type": "serving_endpoint",
        "endpoint": "knowledge_assistant",
        "description": (
            "Query the knowledge-assistant endpoint on Model Serving. "
            "Use this for documentation and policy lookups. "
            "The endpoint must have task type agent/v1/responses."
        ),
    },
    {
        "name": "lakebase_vector",
        "type": "serving_endpoint",
        "endpoint": "lakebase_vector_storage",
        "description": (
            "Query the Lakebase-backed vector storage endpoint on Model Serving. "
            "Use this for semantic retrieval and vector-search style lookups. "
            "The endpoint must have task type agent/v1/responses."
        ),
    },
]

if not SUBAGENTS:
    logging.getLogger(__name__).warning(
        "No subagents configured in SUBAGENTS. Running without backend routing tools until configured."
    )
else:
    # Validate required fields at startup to catch config errors early.
    for _sa in SUBAGENTS:
        _required = {"name", "type", "description"}
        _required.add("space_id" if _sa.get("type") == "genie" else "endpoint")
        _missing = _required - _sa.keys()
        if _missing:
            raise ValueError(
                f"SUBAGENTS entry {_sa.get('name', '?')!r} is missing required fields: {_missing}"
            )

# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

# NOTE: a single client instance is shared: set as the Agents SDK default and
# reused explicitly in tool functions to avoid creating redundant connections.
_client = AsyncDatabricksOpenAI()
set_default_openai_client(_client)
set_default_openai_api("chat_completions")
set_trace_processors([])  # only use mlflow for trace processing
mlflow.openai.autolog()
logging.getLogger("mlflow.utils.autologging_utils").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Subagent tools — one tool per non-genie SUBAGENTS entry
# ---------------------------------------------------------------------------


def _make_subagent_tool(subagent: dict[str, Any]):
    """Create a function_tool for a single subagent definition."""
    endpoint = subagent["endpoint"]
    model = f"apps/{endpoint}" if subagent["type"] == "app" else endpoint

    async def _call(question: str) -> str:
        response = await _client.responses.create(
            model=model,
            input=[{"role": "user", "content": question}],
        )
        return response.output_text

    # Give the function a unique name and docstring so the orchestrator
    # sees it as a distinct, well-described tool.
    _call.__name__ = f"query_{subagent['name']}"
    _call.__doc__ = subagent["description"]
    return function_tool(_call)


subagent_tools = [_make_subagent_tool(sa) for sa in SUBAGENTS if sa["type"] != "genie"]


# ---------------------------------------------------------------------------
# MCP server + orchestrator agent
# ---------------------------------------------------------------------------


def build_mcp_servers() -> list[McpServer]:
    """Build a Genie MCP server for each genie subagent configured (usually 0 or 1)."""
    return [
        McpServer(
            url=build_mcp_url(f"/api/2.0/mcp/genie/{sa['space_id']}"), name="Genie"
        )
        for sa in SUBAGENTS
        if sa["type"] == "genie"
    ]


async def connect_healthy_mcp_servers(
    stack: AsyncExitStack, servers: list[McpServer]
) -> tuple[list[McpServer], list[str]]:
    """Connect each MCP server and verify it can actually list its tools.

    The Agents SDK lists each server's tools lazily inside ``Runner.run``, so a server that
    connects but fails at list time (e.g. an unauthorized Genie space) would otherwise crash
    the whole request — including the unrelated subagent tools. We list tools here, per
    server: healthy servers are kept; any that fails to connect OR to list is dropped and its
    name returned, so the orchestrator runs with whatever is available instead of erroring out.

    Returns (healthy_servers, unavailable_names).
    """
    healthy: list[McpServer] = []
    unavailable: list[str] = []
    for server in servers:
        name = getattr(server, "name", "MCP server")
        try:
            connected = await stack.enter_async_context(server)
            await connected.list_tools()  # forces the connectivity + authorization check now
            healthy.append(connected)
        except Exception:
            logger.warning(
                "MCP server %r unavailable; continuing without it.", name, exc_info=True
            )
            unavailable.append(name)
    return healthy, unavailable


def create_orchestrator_agent(
    mcp_servers: list[McpServer], unavailable_tools: list[str] | None = None
) -> Agent:
    """Build the orchestrator agent with dynamically generated instructions."""
    # Build routing instructions from the configured SUBAGENTS so they stay
    # in sync with the actual tools without manual updates.
    tool_lines = []
    for sa in SUBAGENTS:
        if sa["type"] == "genie":
            tool_lines.append(f"- Genie MCP tools ({sa['name']}): {sa['description']}")
        else:
            tool_lines.append(f"- query_{sa['name']}: {sa['description']}")

    if tool_lines:
        instructions = (
            "You are an orchestrator agent. Route the user's request to the most "
            f"appropriate tool:\n"
            + "\n".join(tool_lines)
            + "\nIf unsure, ask the user for clarification."
        )
    else:
        instructions = (
            "You are an assistant. No routing tools are configured. "
            "Answer based on your own knowledge."
        )

    if unavailable_tools:
        names = ", ".join(sorted(set(unavailable_tools)))
        instructions += (
            f"\n\nThese tools are currently UNAVAILABLE: {names}. "
            "If answering requires one of them, tell the user it isn't available "
            "instead of guessing."
        )

    return Agent(
        name="Orchestrator",
        instructions=instructions,
        model=ORCHESTRATOR_MODEL,
        mcp_servers=mcp_servers,
        tools=subagent_tools,
    )


# ---------------------------------------------------------------------------
# MLflow Responses API handlers
# ---------------------------------------------------------------------------


def _to_messages(input_items) -> list[dict[str, Any]]:
    """Normalize MLflow ResponseInputItems to plain role/content dicts.

    MLflow's Pydantic model adds a ``type: "message"`` field when parsing
    input dicts. The openai-agents SDK's chat completions converter then tries
    to iterate string content as a list of content blocks, raising
    ``TypeError: string indices must be integers``. This function strips all
    framework-added fields and flattens list content to a plain string so the
    SDK receives the simple ``{"role": ..., "content": ...}`` format it expects.
    """
    messages = []
    for item in input_items:
        d = item.model_dump() if hasattr(item, "model_dump") else item
        if not isinstance(d, dict):
            continue
        role = d.get("role")
        if not role:
            continue
        content = d.get("content", "")
        if isinstance(content, list):
            # Flatten Responses API content blocks to a single string.
            texts = [
                b.get("text", "") if isinstance(b, dict) else str(b) for b in content
            ]
            content = " ".join(filter(None, texts))
        messages.append({"role": role, "content": content})
    return messages


def _extract_mcp_errors(exc: Exception) -> list[UserError]:
    """Return any UserError instances from a direct exception or ExceptionGroup."""
    if isinstance(exc, UserError):
        return [exc]
    if isinstance(exc, BaseExceptionGroup):
        return [e for e in exc.exceptions if isinstance(e, UserError)]
    return []


@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    if session_id := get_session_id(request):
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})
    try:
        async with AsyncExitStack() as stack:
            servers, unavailable = await connect_healthy_mcp_servers(
                stack, build_mcp_servers()
            )
            agent = create_orchestrator_agent(servers, unavailable)
            messages = _to_messages(request.input)
            result = await Runner.run(agent, messages)
            return ResponsesAgentResponse(
                output=[item.to_input_item() for item in result.new_items]
            )
    except Exception as e:
        mcp_errors = _extract_mcp_errors(e)
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
    if session_id := get_session_id(request):
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})
    try:
        async with AsyncExitStack() as stack:
            servers, unavailable = await connect_healthy_mcp_servers(
                stack, build_mcp_servers()
            )
            agent = create_orchestrator_agent(servers, unavailable)
            messages = _to_messages(request.input)
            result = Runner.run_streamed(agent, input=messages)
            async for event in process_agent_stream_events(result.stream_events()):
                yield event
    except Exception as e:
        mcp_errors = _extract_mcp_errors(e)
        if mcp_errors:
            logger.warning(
                "MCP tool error during stream: %s",
                "; ".join(str(x) for x in mcp_errors),
            )
            return
        raise
