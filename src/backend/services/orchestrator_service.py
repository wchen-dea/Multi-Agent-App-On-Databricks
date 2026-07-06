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


def _format_unavailable_reason(name: str, exc: Exception) -> str:
    """Format a concise unavailable reason with exception details.

    Args:
        name: Display name of the unavailable dependency.
        exc: Original exception raised during availability check.

    Returns:
        Human-readable unavailable reason including exception type and detail.

    Notes:
        Appends cause details when present and distinct from the top-level
        exception message.
    """
    detail = str(exc).strip() or "no error details"
    reason = f"{name} unavailable: {type(exc).__name__}: {detail}"
    cause = exc.__cause__ or exc.__context__
    if cause is not None:
        cause_detail = str(cause).strip()
        if cause_detail and cause_detail != detail:
            reason += f" (caused by {type(cause).__name__}: {cause_detail})"
    return reason


@dataclass(frozen=True)
class OrchestratorDependencies:
    """Group injectable dependencies used by orchestration helpers.

    Attributes:
        trace_metadata_updater: Callable that records tool/auth metadata in the
            active trace span.
        function_tool_wrapper: Wrapper used to expose async callables as OpenAI
            function tools.
        mcp_server_factory: Factory used to construct MCP server descriptors.
        message_bus: Event sink for tool and MCP lifecycle signals.
    """

    trace_metadata_updater: TraceMetadataUpdater = mlflow.update_current_trace
    function_tool_wrapper: FunctionToolWrapper = function_tool
    mcp_server_factory: McpServerFactory = McpServer
    message_bus: MessageBus = NoOpMessageBus()


def _trace_tool_auth(
    subagent: SubagentConfig,
    has_user_identity: bool,
    deps: OrchestratorDependencies,
) -> None:
    """Record per-tool auth selection metadata in the current trace.

    Args:
        subagent: Subagent being invoked.
        has_user_identity: Whether request includes user identity for OBO.
        deps: Orchestrator dependencies with trace updater.

    Side Effects:
        Writes tool auth metadata to the active trace span.
    """
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
    """Select app or OBO client for a subagent.

    Args:
        subagent: Subagent configuration containing auth mode.
        app_client: App-identity Databricks OpenAI client.
        obo_client: Optional user-identity Databricks OpenAI client.

    Returns:
        The client authorized for the subagent's auth mode.

    Raises:
        UserError: If the subagent requires OBO and user identity is missing.
    """
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
    """Build function tools for non-MCP subagents.

    Args:
        subagents: Loaded and validated subagent configuration entries.
        app_client: Databricks OpenAI client bound to app identity.
        obo_client: Optional Databricks OpenAI client bound to forwarded user
            identity for OBO-only tools.
        deps: Optional dependency overrides for testing and instrumentation.

    Returns:
        A list of wrapped function tools that can be attached to the
        orchestrator agent.

    Raises:
        UserError: If an OBO subagent is invoked but no user token-backed
            client is available.

    Side Effects:
        Publishes tool start/success/failure events on the message bus and
        updates trace metadata with auth selection context.
    """
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
                tool_input = [{"role": "user", "content": question}]
                if subagent_cfg_param.system_prompt:
                    tool_input = [
                        {"role": "system", "content": subagent_cfg_param.system_prompt},
                        *tool_input,
                    ]
                response = await selected_client.responses.create(
                    model=subagent_cfg_param.model_name,
                    input=tool_input,
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
        if subagent.is_genie or subagent.is_mcp:
            continue
        tools.append(dependencies.function_tool_wrapper(_make_tool(subagent)))
    return tools


def build_mcp_servers(
    subagents: list[SubagentConfig],
    identity_ctx: RequestIdentityContext,
    deps: OrchestratorDependencies | None = None,
) -> tuple[list[McpServer], list[str]]:
    """Build MCP server descriptors for Genie and generic MCP subagents.

    Args:
        subagents: Loaded and validated subagent configuration entries.
        identity_ctx: Request-scoped app and user identity clients.
        deps: Optional dependency overrides for testing and instrumentation.

    Returns:
        A tuple of:
        - MCP server descriptors eligible for connection attempts.
        - Human-readable unavailable reasons detected during pre-check.

    Side Effects:
        Publishes MCP registration/unavailable lifecycle events.

    Notes:
        OBO-configured MCP subagents are excluded when user identity is not
        available in the request context.
    """
    dependencies = deps or OrchestratorDependencies()
    servers: list[McpServer] = []
    unavailable: list[str] = []

    for subagent in subagents:
        if not subagent.is_genie and not subagent.is_mcp:
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

        if subagent.is_genie:
            url = build_mcp_url(
                f"/api/2.0/mcp/genie/{subagent.space_id}",
                workspace_client=workspace_client,
            )
            server_name = f"Genie:{subagent.name}"
        else:
            url = build_mcp_url(subagent.mcp_url or "", workspace_client=workspace_client)
            server_name = f"MCP:{subagent.name}"

        servers.append(
            dependencies.mcp_server_factory(
                url=url,
                name=server_name,
                workspace_client=workspace_client,
            )
        )
        dependencies.message_bus.publish(
            "mcp.server.registered",
            {
                "subagent": subagent.name,
                "auth_mode": subagent.auth_mode,
                "space_id": subagent.space_id,
                "mcp_url": subagent.mcp_url,
            },
        )

    return servers, unavailable


async def connect_healthy_mcp_servers(
    stack: AsyncExitStack, servers: list[McpServer]
) -> tuple[list[McpServer], list[str]]:
    """Connect MCP servers and retain only healthy endpoints.

    Args:
        stack: Async context stack used to own connected server lifecycles.
        servers: Candidate MCP servers created from subagent configuration.

    Returns:
        A tuple of:
        - Connected MCP servers that successfully responded to `list_tools`.
        - Unavailable reason strings for failed connection attempts.

    Side Effects:
        Enters async contexts on successful servers and logs failures.
    """
    healthy: list[McpServer] = []
    unavailable: list[str] = []

    for server in servers:
        name = getattr(server, "name", "MCP server")
        try:
            connected = await stack.enter_async_context(server)
            await connected.list_tools()
            healthy.append(connected)
        except Exception as exc:
            reason = _format_unavailable_reason(name, exc)
            logger.warning(
                "MCP server %r unavailable (%s); continuing without it.",
                name,
                reason,
                exc_info=True,
            )
            unavailable.append(reason)

    return healthy, unavailable


def create_orchestrator_agent(
    model: str,
    subagents: list[SubagentConfig],
    mcp_servers: list,
    tools: list,
    unavailable_tools: list[str] | None = None,
) -> Agent:
    """Create an orchestrator agent with runtime-aware routing instructions.

    Args:
        model: Model identifier for orchestrator responses.
        subagents: Active subagent configuration entries used to derive
            tool-routing instructions.
        mcp_servers: Connected MCP servers attached to the orchestrator.
        tools: Wrapped function tools attached to the orchestrator.
        unavailable_tools: Optional unavailable tool/runtime reasons injected
            into instructions.

    Returns:
        A configured `Agent` instance ready for request handling.

    Notes:
        Instruction text enforces evidence requirements for tools marked with
        `requires_evidence=true`.
    """
    tool_lines: list[str] = []
    for subagent in subagents:
        if subagent.is_genie or subagent.is_mcp:
            base = (
                "- MCP tools "
                f"({subagent.name}, auth={subagent.auth_mode}, "
                f"classification={subagent.data_classification}, evidence={subagent.requires_evidence}): "
                f"{subagent.description}"
            )
        else:
            base = (
                f"- {subagent.tool_name} (auth={subagent.auth_mode}, "
                f"classification={subagent.data_classification}, evidence={subagent.requires_evidence}): "
                f"{subagent.description}"
            )

        if subagent.system_prompt:
            base += f"\n  System prompt: {subagent.system_prompt}"
        tool_lines.append(base)

    if tool_lines:
        instructions = (
            "You are an orchestrator agent. Route the user's request to the most "
            "appropriate tool:\n"
            + "\n".join(tool_lines)
            + "\nIf unsure, ask the user for clarification."
            + "\nFor any answer grounded in a tool marked evidence=true, include evidence in the final answer."
            + "\nUse either inline citations like `[1]` or end with a `Source:` line naming the tool and freshness SLA."
            + "\nDo not give a governed final answer without that evidence line."
        )
    else:
        instructions = (
            "You are an assistant. No routing tools are configured. "
            "Answer based on your own knowledge."
        )

    if unavailable_tools:
        names = "\n- " + "\n- ".join(sorted(set(unavailable_tools)))
        instructions += (
            "\n\nUnavailable tool/runtime details:"
            f"{names}\n"
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
