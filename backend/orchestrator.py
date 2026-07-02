"""Provide orchestration helpers for tools, MCP connectivity, and agent assembly."""

import logging
from contextlib import AsyncExitStack

from agents import Agent, function_tool
from databricks_openai import AsyncDatabricksOpenAI
from databricks_openai.agents import McpServer

from backend.subagent_config import SubagentConfig
from backend.utils import build_mcp_url

logger = logging.getLogger(__name__)


def build_subagent_tools(
    subagents: list[SubagentConfig], client: AsyncDatabricksOpenAI
) -> list:
    """Build callable tools for all non-Genie subagents.

    Args:
        subagents: Parsed subagent configuration entries.
        client: Shared Databricks OpenAI client.

    Returns:
        List of function_tool wrappers for non-Genie subagents.
    """
    tools = []
    for subagent in subagents:
        if subagent.is_genie:
            continue

        async def _call(question: str, _subagent: SubagentConfig = subagent) -> str:
            response = await client.responses.create(
                model=_subagent.model_name,
                input=[{"role": "user", "content": question}],
            )
            return response.output_text

        _call.__name__ = subagent.tool_name
        _call.__doc__ = subagent.description
        tools.append(function_tool(_call))
    return tools


def build_mcp_servers(subagents: list[SubagentConfig]) -> list[McpServer]:
    """Build Genie MCP server definitions from subagent configuration.

    Args:
        subagents: Parsed subagent configuration entries.

    Returns:
        MCP server definitions for Genie-backed subagents.
    """
    return [
        McpServer(url=build_mcp_url(f"/api/2.0/mcp/genie/{subagent.space_id}"), name="Genie")
        for subagent in subagents
        if subagent.is_genie
    ]


async def connect_healthy_mcp_servers(
    stack: AsyncExitStack, servers: list[McpServer]
) -> tuple[list[McpServer], list[str]]:
    """Connect MCP servers and return healthy servers plus unavailable names.

    Args:
        stack: Async exit stack managing server lifetimes.
        servers: Candidate MCP server definitions.

    Returns:
        Tuple of connected healthy servers and unavailable server names.
    """
    healthy: list[McpServer] = []
    unavailable: list[str] = []

    for server in servers:
        name = getattr(server, "name", "MCP server")
        try:
            connected = await stack.enter_async_context(server)
            await connected.list_tools()
            healthy.append(connected)
        except Exception:
            logger.warning(
                "MCP server %r unavailable; continuing without it.", name, exc_info=True
            )
            unavailable.append(name)

    return healthy, unavailable


def create_orchestrator_agent(
    model: str,
    subagents: list[SubagentConfig],
    mcp_servers: list[McpServer],
    tools: list,
    unavailable_tools: list[str] | None = None,
) -> Agent:
    """Create the orchestrator Agent with runtime-aware tool instructions.

    Args:
        model: Model identifier for the orchestrator.
        subagents: Parsed subagent configuration entries.
        mcp_servers: Connected MCP servers.
        tools: Non-MCP callable tools.
        unavailable_tools: Names of unavailable tools to disclose.

    Returns:
        Configured orchestrator agent instance.
    """
    tool_lines = [
        f"- Genie MCP tools ({subagent.name}): {subagent.description}"
        if subagent.is_genie
        else f"- {subagent.tool_name}: {subagent.description}"
        for subagent in subagents
    ]

    if tool_lines:
        instructions = (
            "You are an orchestrator agent. Route the user's request to the most "
            "appropriate tool:\n"
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
        model=model,
        mcp_servers=mcp_servers,
        tools=tools,
    )
