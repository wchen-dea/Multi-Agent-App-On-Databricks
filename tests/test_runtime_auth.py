from types import SimpleNamespace

from backend.domain.subagent_config import SubagentConfig
from backend.services.runtime_auth_service import (
    RuntimeAuthDependencies,
    build_runtime_auth_context,
)
from mlflow.types.responses import ResponsesAgentRequest


def _sample_subagents() -> list[SubagentConfig]:
    return [
        SubagentConfig(
            name="sales_agent",
            kind="genie",
            auth_mode="obo",
            space_id="space-1",
            description="genie",
        ),
        SubagentConfig(
            name="knowledge_assistant",
            kind="serving_endpoint",
            auth_mode="app",
            endpoint="knowledge_assistant",
            description="serving",
        ),
    ]


def test_build_runtime_auth_context_without_user_identity():
    subagents = _sample_subagents()
    app_client = object()
    trace_payload = {}

    identity_ctx = SimpleNamespace(
        has_user_identity=False,
        user_workspace_client=None,
        app_workspace_client=object(),
    )
    def fake_build_subagent_tools(s, app, obo):
        assert s == subagents
        assert app is app_client
        assert obo is None
        return ["tool-a"]

    deps = RuntimeAuthDependencies(
        identity_context_provider=lambda: identity_ctx,
        session_id_provider=lambda req: "conv-1",
        trace_metadata_updater=lambda metadata: trace_payload.update(metadata),
        subagent_tools_builder=fake_build_subagent_tools,
        mcp_servers_builder=lambda s, ctx: (["mcp-a"], ["missing-obo"]),
    )

    request = ResponsesAgentRequest(input=[])
    ctx = build_runtime_auth_context(
        request=request,
        subagents=subagents,
        app_client=app_client,
        deps=deps,
    )

    assert ctx.subagent_tools == ["tool-a"]
    assert ctx.mcp_servers == ["mcp-a"]
    assert ctx.unavailable_auth == ["missing-obo"]
    assert trace_payload["auth.user_token_present"] == "false"
    assert trace_payload["mlflow.trace.session"] == "conv-1"


def test_build_runtime_auth_context_with_user_identity():
    subagents = _sample_subagents()
    app_client = object()
    trace_payload = {}

    identity_ctx = SimpleNamespace(
        has_user_identity=True,
        user_workspace_client=object(),
        app_workspace_client=object(),
    )
    obo_client = object()

    def fake_obo_client_factory(workspace_client):
        assert workspace_client is identity_ctx.user_workspace_client
        return obo_client

    def fake_build_subagent_tools(s, app, obo):
        assert s == subagents
        assert app is app_client
        assert obo is obo_client
        return ["tool-b"]

    deps = RuntimeAuthDependencies(
        identity_context_provider=lambda: identity_ctx,
        session_id_provider=lambda req: None,
        trace_metadata_updater=lambda metadata: trace_payload.update(metadata),
        obo_client_factory=fake_obo_client_factory,
        subagent_tools_builder=fake_build_subagent_tools,
        mcp_servers_builder=lambda s, ctx: (["mcp-b"], []),
    )

    request = ResponsesAgentRequest(input=[])
    ctx = build_runtime_auth_context(
        request=request,
        subagents=subagents,
        app_client=app_client,
        deps=deps,
    )

    assert ctx.subagent_tools == ["tool-b"]
    assert ctx.mcp_servers == ["mcp-b"]
    assert ctx.unavailable_auth == []
    assert trace_payload["auth.user_token_present"] == "true"
