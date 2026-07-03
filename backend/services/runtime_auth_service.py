"""Build request-scoped runtime auth context for hybrid app/OBO execution."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import mlflow
from databricks_openai import AsyncDatabricksOpenAI
from databricks_openai.agents import McpServer
from mlflow.types.responses import ResponsesAgentRequest

from backend.domain.subagent_config import SubagentConfig
from backend.services.interfaces import (
    IdentityContextProvider,
    McpServersBuilder,
    MessageBus,
    OboClientFactory,
    SessionIdProvider,
    SubagentToolsBuilder,
    TraceMetadataUpdater,
)
from backend.services.message_bus import NoOpMessageBus
from backend.services.orchestrator_service import build_mcp_servers, build_subagent_tools
from backend.services.policy_service import (
    PolicyDecision,
    PolicyContext,
    build_policy_context,
    filter_subagents_by_policy,
)
from backend.shared.runtime_utils import (
    RequestIdentityContext,
    build_request_identity_context,
    get_session_id,
)


@dataclass(frozen=True)
class RuntimeAuthContext:
    """Precomputed per-request auth/runtime dependencies for handler execution."""

    subagent_tools: list
    mcp_servers: list[McpServer]
    unavailable_auth: list[str]
    policy_allowed_subagents: list[SubagentConfig]


@dataclass(frozen=True)
class RuntimeAuthDependencies:
    """Injectable dependencies for building runtime auth context."""

    identity_context_provider: IdentityContextProvider = build_request_identity_context
    session_id_provider: SessionIdProvider = get_session_id
    trace_metadata_updater: TraceMetadataUpdater = mlflow.update_current_trace
    obo_client_factory: OboClientFactory = AsyncDatabricksOpenAI
    subagent_tools_builder: SubagentToolsBuilder = build_subagent_tools
    mcp_servers_builder: McpServersBuilder = build_mcp_servers
    policy_context_builder: Callable[
        [ResponsesAgentRequest, RequestIdentityContext], PolicyContext
    ] = build_policy_context
    subagent_policy_filter: Callable[
        [list[SubagentConfig], PolicyContext], tuple[list[SubagentConfig], list[PolicyDecision]]
    ] = filter_subagents_by_policy
    message_bus: MessageBus = NoOpMessageBus()


def _build_trace_metadata(
    subagents: list[SubagentConfig],
    request: ResponsesAgentRequest,
    identity_ctx: RequestIdentityContext,
    deps: RuntimeAuthDependencies,
) -> dict[str, str]:
    """Build and emit request trace metadata for hybrid app/OBO authorization."""
    metadata: dict[str, str] = {
        "auth.user_token_present": str(identity_ctx.has_user_identity).lower(),
        "auth.subagents_total": str(len(subagents)),
        "auth.subagents_obo": str(sum(1 for s in subagents if s.is_obo)),
        "auth.subagents_app": str(sum(1 for s in subagents if not s.is_obo)),
    }
    if session_id := deps.session_id_provider(request):
        metadata["mlflow.trace.session"] = session_id
    deps.trace_metadata_updater(metadata=metadata)
    deps.message_bus.publish("auth.trace.metadata.updated", metadata)
    return metadata


def build_runtime_auth_context(
    request: ResponsesAgentRequest,
    subagents: list[SubagentConfig],
    app_client: AsyncDatabricksOpenAI,
    deps: RuntimeAuthDependencies | None = None,
) -> RuntimeAuthContext:
    """Build request-scoped clients and tool wiring for hybrid auth execution."""
    dependencies = deps or RuntimeAuthDependencies()
    identity_ctx = dependencies.identity_context_provider()
    policy_ctx = dependencies.policy_context_builder(request, identity_ctx)

    allowed_subagents, policy_decisions = dependencies.subagent_policy_filter(subagents, policy_ctx)
    denied_by_policy = [d.reason for d in policy_decisions if not d.allowed]

    for decision in policy_decisions:
        dependencies.message_bus.publish(
            "policy.subagent.decision",
            {
                "result": "allow" if decision.allowed else "deny",
                "subagent": decision.subagent_name,
                "tool_name": decision.tool_name,
                "reason_code": decision.reason_code,
                "reason": decision.reason,
                "persona": policy_ctx.persona or "<missing>",
                "has_user_identity": policy_ctx.has_user_identity,
                "requested_tool": policy_ctx.requested_tool or "<unspecified>",
                "request_confidence": policy_ctx.request_confidence,
            },
        )

    dependencies.message_bus.publish(
        "auth.identity.resolved",
        {
            "has_user_identity": identity_ctx.has_user_identity,
            "subagents_total": len(subagents),
        },
    )
    _build_trace_metadata(subagents, request, identity_ctx, dependencies)

    obo_client = (
        dependencies.obo_client_factory(workspace_client=identity_ctx.user_workspace_client)
        if identity_ctx.has_user_identity
        else None
    )

    subagent_tools = dependencies.subagent_tools_builder(allowed_subagents, app_client, obo_client)
    mcp_servers, unavailable_auth = dependencies.mcp_servers_builder(allowed_subagents, identity_ctx)
    unavailable = denied_by_policy + unavailable_auth
    dependencies.message_bus.publish(
        "auth.context.built",
        {
            "subagent_tools": len(subagent_tools),
            "mcp_servers": len(mcp_servers),
            "unavailable_auth": len(unavailable),
        },
    )
    return RuntimeAuthContext(
        subagent_tools=subagent_tools,
        mcp_servers=mcp_servers,
        unavailable_auth=unavailable,
        policy_allowed_subagents=allowed_subagents,
    )
