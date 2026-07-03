"""Provide orchestration helpers for tools, MCP connectivity, and agent assembly."""

from dataclasses import dataclass
import logging
from contextlib import AsyncExitStack
from typing import Any

import mlflow
from agents import Agent, function_tool
from agents.exceptions import UserError
from databricks_openai import AsyncDatabricksOpenAI
from databricks_openai.agents import McpServer

from backend.domain.subagent_config import SubagentConfig
from backend.services.interfaces import (
    FunctionToolWrapper,
    McpServerFactory,
    MessageBus,
    TraceMetadataUpdater,
)
from backend.services.message_bus import NoOpMessageBus
from backend.shared.runtime_utils import RequestIdentityContext, build_mcp_url

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrchestratorDependencies:
    """Injectable dependencies for orchestration service functions."""

    trace_metadata_updater: TraceMetadataUpdater = mlflow.update_current_trace
    function_tool_wrapper: FunctionToolWrapper = function_tool
    mcp_server_factory: McpServerFactory = McpServer
    message_bus: MessageBus = NoOpMessageBus()


def _trace_tool_auth(
    subagent: SubagentConfig,
    has_user_identity: bool,
    deps: OrchestratorDependencies,
) -> None:
    """Record per-tool auth selection metadata in the current trace."""
    deps.trace_metadata_updater(
        metadata={
            "auth.tool_name": subagent.tool_name,
            "auth.auth_mode_selected": subagent.auth_mode,
            "auth.user_token_present": str(has_user_identity).lower(),
        }
    )


def _select_tool_client(
    subagent: SubagentConfig,
    app_client: AsyncDatabricksOpenAI,
    obo_client: AsyncDatabricksOpenAI | None,
) -> AsyncDatabricksOpenAI:
    """Select app or OBO client for a subagent and raise clear auth errors."""
    if not subagent.is_obo:
        return app_client
    if obo_client is None:
        raise UserError(
            "This tool requires user authorization (OBO), but no forwarded "
            "access token was provided. Re-authenticate and try again."
        )
    return obo_client


def build_subagent_tools(
    subagents: list[SubagentConfig],
    app_client: AsyncDatabricksOpenAI,
    obo_client: AsyncDatabricksOpenAI | None,
    deps: OrchestratorDependencies | None = None,
) -> list:
    """Build callable tools for all non-Genie subagents."""
    dependencies = deps or OrchestratorDependencies()
    tools = []

    def _make_tool(subagent_cfg: SubagentConfig):
        async def _call(question: str, subagent_cfg_param: SubagentConfig = subagent_cfg) -> str:
            dependencies.message_bus.publish(
                "tool.call.started",
                {
                    "tool_name": subagent_cfg_param.tool_name,
                    "subagent": subagent_cfg_param.name,
                    "auth_mode": subagent_cfg_param.auth_mode,
                },
            )
            selected_client = _select_tool_client(subagent_cfg_param, app_client, obo_client)
            _trace_tool_auth(
                subagent_cfg_param,
                has_user_identity=obo_client is not None,
                deps=dependencies,
            )
            try:
                response = await selected_client.responses.create(
                    model=subagent_cfg_param.model_name,
                    input=[{"role": "user", "content": question}],
                )
                dependencies.message_bus.publish(
                    "tool.call.succeeded",
                    {
                        "tool_name": subagent_cfg_param.tool_name,
                        "subagent": subagent_cfg_param.name,
                        "auth_mode": subagent_cfg_param.auth_mode,
                    },
                )
                return response.output_text
            except Exception as exc:
                dependencies.message_bus.publish(
                    "tool.call.failed",
                    {
                        "tool_name": subagent_cfg_param.tool_name,
                        "subagent": subagent_cfg_param.name,
                        "auth_mode": subagent_cfg_param.auth_mode,
                        "error_type": type(exc).__name__,
                    },
                )
                raise

        _call.__name__ = subagent_cfg.tool_name
        _call.__doc__ = subagent_cfg.description
        return _call

    for subagent in subagents:
        if subagent.is_genie:
            continue
        tools.append(dependencies.function_tool_wrapper(_make_tool(subagent)))
    return tools


def build_mcp_servers(
    subagents: list[SubagentConfig],
    identity_ctx: RequestIdentityContext,
    deps: OrchestratorDependencies | None = None,
) -> tuple[list[McpServer], list[str]]:
    """Build Genie MCP server definitions from subagent configuration."""
    dependencies = deps or OrchestratorDependencies()
    servers: list[McpServer] = []
    unavailable: list[str] = []

    for subagent in subagents:
        if not subagent.is_genie:
            continue

        if subagent.is_obo:
            if not identity_ctx.has_user_identity:
                unavailable.append(
                    f"Genie MCP tools ({subagent.name}) requires user authorization (OBO)"
                )
                dependencies.message_bus.publish(
                    "mcp.server.unavailable",
                    {
                        "subagent": subagent.name,
                        "auth_mode": subagent.auth_mode,
                        "reason": "missing_obo_identity",
                    },
                )
                continue
            workspace_client = identity_ctx.user_workspace_client
        else:
            workspace_client = identity_ctx.app_workspace_client

        servers.append(
            dependencies.mcp_server_factory(
                url=build_mcp_url(
                    f"/api/2.0/mcp/genie/{subagent.space_id}",
                    workspace_client=workspace_client,
                ),
                name=f"Genie:{subagent.name}",
                workspace_client=workspace_client,
            )
        )
        dependencies.message_bus.publish(
            "mcp.server.registered",
            {
                "subagent": subagent.name,
                "auth_mode": subagent.auth_mode,
                "space_id": subagent.space_id,
            },
        )

    return servers, unavailable


async def connect_healthy_mcp_servers(
    stack: AsyncExitStack, servers: list[McpServer]
) -> tuple[list[McpServer], list[str]]:
    """Connect MCP servers and return healthy servers plus unavailable names."""
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
    mcp_servers: list,
    tools: list,
    unavailable_tools: list[str] | None = None,
) -> Agent:
    """Create the orchestrator Agent with runtime-aware tool instructions."""
    tool_lines = [
        f"- Genie MCP tools ({subagent.name}, auth={subagent.auth_mode}): {subagent.description}"
        if subagent.is_genie
        else f"- {subagent.tool_name} (auth={subagent.auth_mode}): {subagent.description}"
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
