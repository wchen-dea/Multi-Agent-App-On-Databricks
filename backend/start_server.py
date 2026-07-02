"""Server bootstrap for the MLflow AgentServer runtime."""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from mlflow.genai.agent_server import (
    AgentServer,
    setup_mlflow_git_based_version_tracking,
)

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)


if not os.getenv("MLFLOW_EXPERIMENT_ID", "").strip():
    os.environ.pop("MLFLOW_EXPERIMENT_ID", None)


import backend.agent

agent_server = AgentServer("ResponsesAgent", enable_chat_proxy=True)
app = agent_server.app


@app.get("/")
def root():
    """Return a simple service status payload for root path probes."""
    return {
        "status": "ok",
        "message": "Service is running. Use /health for readiness or /invocations for agent requests.",
    }


try:
    setup_mlflow_git_based_version_tracking()
except Exception as exc:
    logging.getLogger(__name__).warning(
        "Skipping MLflow git-based version tracking during local startup: %s", exc
    )


def main():
    """Run the AgentServer application."""
    agent_server.run(app_import_string="backend.start_server:app")
