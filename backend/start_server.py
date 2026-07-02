import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from mlflow.genai.agent_server import AgentServer, setup_mlflow_git_based_version_tracking

# Load env vars from .env before importing the agent for proper auth
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

# Treat an empty value as unset; MLflow raises on MLFLOW_EXPERIMENT_ID="".
if not os.getenv("MLFLOW_EXPERIMENT_ID", "").strip():
    os.environ.pop("MLFLOW_EXPERIMENT_ID", None)

# Need to import the agent to register the functions with the server
import backend.agent  # noqa: E402

agent_server = AgentServer("ResponsesAgent", enable_chat_proxy=True)
# Define the app as a module level variable to enable multiple workers
app = agent_server.app  # noqa: F841


@app.get("/")
def root():
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
    agent_server.run(app_import_string="backend.start_server:app")
