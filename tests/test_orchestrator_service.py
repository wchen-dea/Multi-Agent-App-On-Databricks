import asyncio
from types import SimpleNamespace

from backend.domain.subagent_config import SubagentConfig
from backend.services.orchestrator_service import (
    OrchestratorDependencies,
    build_mcp_servers,
    build_subagent_tools,
)


def test_build_subagent_tools_uses_injected_wrapper_and_trace_updater():
    subagents = [
        SubagentConfig(
            name="knowledge_assistant",
            kind="serving_endpoint",
            auth_mode="app",
            endpoint="knowledge_assistant",
            description="serving",
        )
    ]

    class FakeResponses:
        async def create(self, model, input):
            assert model == "knowledge_assistant"
            assert input[0]["content"] == "hello"
            return SimpleNamespace(output_text="ok")

    app_client = SimpleNamespace(responses=FakeResponses())
    trace_payload = {}

    deps = OrchestratorDependencies(
        trace_metadata_updater=lambda metadata: trace_payload.update(metadata),
        function_tool_wrapper=lambda func: func,
    )

    tools = build_subagent_tools(subagents, app_client, None, deps=deps)
    assert len(tools) == 1

    result = asyncio.run(tools[0]("hello"))

    assert result == "ok"
    assert trace_payload["auth.tool_name"] == "query_knowledge_assistant"
    assert trace_payload["auth.auth_mode_selected"] == "app"
    assert trace_payload["auth.user_token_present"] == "false"


def test_build_mcp_servers_uses_factory_and_tracks_obo_unavailable():
    subagents = [
        SubagentConfig(
            name="sales_obo",
            kind="genie",
            auth_mode="obo",
            space_id="space-obo",
            description="genie obo",
        ),
        SubagentConfig(
            name="sales_app",
            kind="genie",
            auth_mode="app",
            space_id="space-app",
            description="genie app",
        ),
    ]

    identity_ctx = SimpleNamespace(
        has_user_identity=False,
        user_workspace_client=None,
        app_workspace_client=object(),
    )

    created = []

    def fake_mcp_server_factory(**kwargs):
        created.append(kwargs)
        return kwargs

    deps = OrchestratorDependencies(mcp_server_factory=fake_mcp_server_factory)

    servers, unavailable = build_mcp_servers(subagents, identity_ctx, deps=deps)

    assert len(servers) == 1
    assert len(created) == 1
    assert created[0]["name"] == "Genie:sales_app"
    assert "space-app" in created[0]["url"]
    assert unavailable == ["Genie MCP tools (sales_obo) requires user authorization (OBO)"]
