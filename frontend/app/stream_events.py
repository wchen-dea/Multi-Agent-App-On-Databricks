"""Streaming event helpers for text and provenance extraction."""

from typing import Any


def extract_delta(event: dict[str, Any]) -> str:
    """Extract a text token from a streamed Responses API event."""
    if event.get("type") != "response.output_text.delta":
        return ""
    delta = event.get("delta", "")
    return str(delta) if delta else ""


def extract_source_hints(event: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Infer source categories and exact tool names from one stream event."""
    categories: set[str] = set()
    tools: set[str] = set()

    event_type = str(event.get("type", ""))
    item = event.get("item") if isinstance(event.get("item"), dict) else None
    item_type = str(item.get("type", "")) if item else ""

    if "mcp" in event_type or "mcp" in item_type:
        categories.add("Genie MCP")

    if event_type.startswith("response.output_item") and item_type == "tool_call_output_item":
        categories.add("Tool Execution")

    for candidate in (
        event.get("name"),
        item.get("name") if item else None,
        item.get("tool_name") if item else None,
    ):
        if isinstance(candidate, str) and candidate.strip():
            tool_name = candidate.strip()
            tools.add(tool_name)
            if tool_name.startswith("query_"):
                categories.add("Serving Endpoint Tool")
            else:
                categories.add("Function Tool")

    return categories, tools
