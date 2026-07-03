"""Presentation-oriented content builders for the Chainlit UI."""

import chainlit as cl

from frontend.app.session import token_status_line


def welcome_message(
    company_name: str,
    company_tagline: str,
    chat_greeting: str,
    set_token_command: str,
    clear_token_command: str,
) -> str:
    """Build the branded welcome panel shown at chat start."""
    return (
        f"## {company_name} AI Workspace\n"
        f"{company_tagline}\n\n"
        f"{chat_greeting}\n\n"
        "### What I can help with\n"
        "- Query business insights through Genie spaces\n"
        "- Route requests to specialist serving endpoint agents\n"
        "- Coordinate cross-tool workflows in one conversation\n\n"
        "### Session Commands\n"
        f"- `{set_token_command} <databricks_access_token>`: enable OBO token forwarding\n"
        f"- `{clear_token_command}`: disable OBO token forwarding for this session\n\n"
        f"{token_status_line()}"
    )


def starter_prompts() -> list[cl.Starter]:
    """Return curated starter prompts for common enterprise workflows."""
    return [
        cl.Starter(
            label="Sales Pulse",
            message="Summarize weekly sales trends and highlight top 3 drivers.",
        ),
        cl.Starter(
            label="Customer Churn",
            message="Identify churn risks this quarter and suggest immediate actions.",
        ),
        cl.Starter(
            label="Knowledge Lookup",
            message="Find the latest policy for production rollout approvals.",
        ),
        cl.Starter(
            label="Ops Health Check",
            message="Give me an operations health snapshot and active risks.",
        ),
    ]


def source_badge_line(categories: set[str], tools: set[str]) -> str:
    """Build a markdown provenance footer for an assistant response."""
    if not categories and not tools:
        return ""

    parts: list[str] = []
    if categories:
        parts.append("Sources used: " + " | ".join(sorted(categories)))
    if tools:
        parts.append("Tools: " + " | ".join(sorted(format_tool_label(name) for name in tools)))

    return "\n\n---\n" + "\n".join(parts)


def format_tool_label(tool_name: str) -> str:
    """Convert internal tool identifiers to user-friendly display names."""
    if tool_name.startswith("query_"):
        return tool_name[len("query_") :].replace("_", " ").title()
    return tool_name.replace("_", " ").title()
