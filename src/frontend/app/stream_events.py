"""Streaming event helpers for text and provenance extraction."""

from typing import Any


def update_stream_hints(
    event: dict[str, Any],
    categories: set[str],
    tools: set[str],
) -> str:
    """Extract text delta and update provenance hints in one pass.

    This mutation-based path avoids per-event temporary set allocations.
    """
    event_type_raw = event.get("type")
    event_type = event_type_raw if isinstance(event_type_raw, str) else ""

    delta = ""
    if event_type == "response.output_text.delta":
        delta_raw = event.get("delta")
        if isinstance(delta_raw, str):
            delta = delta_raw
        elif delta_raw:
            delta = str(delta_raw)

    item_raw = event.get("item")
    item = item_raw if isinstance(item_raw, dict) else None
    item_type_raw = item.get("type") if item else ""
    item_type = item_type_raw if isinstance(item_type_raw, str) else ""

    if "mcp" in event_type or "mcp" in item_type:
        categories.add("Genie MCP")

    if event_type.startswith("response.output_item") and item_type == "tool_call_output_item":
        categories.add("Tool Execution")

    candidates = (
        event.get("name"),
        item.get("name") if item else None,
        item.get("tool_name") if item else None,
    )
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        tool_name = candidate.strip()
        if not tool_name:
            continue
        tools.add(tool_name)
        if tool_name.startswith("query_"):
            categories.add("Serving Endpoint Tool")
        else:
            categories.add("Function Tool")

    return delta


def analyze_stream_event(event: dict[str, Any]) -> tuple[str, set[str], set[str]]:
    """Extract text delta and provenance hints in one pass.

    Returns:
        Tuple of (delta_text, source_categories, source_tool_names).
    """
    categories: set[str] = set()
    tools: set[str] = set()
    delta = update_stream_hints(event, categories, tools)
    return delta, categories, tools


def extract_delta(event: dict[str, Any]) -> str:
    """Extract a text token from a streamed Responses API event."""
    delta, _, _ = analyze_stream_event(event)
    return delta


def extract_source_hints(event: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Infer source categories and exact tool names from one stream event."""
    _, categories, tools = analyze_stream_event(event)
    return categories, tools
