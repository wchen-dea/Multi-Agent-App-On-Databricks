"""Runtime settings for backend services."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AppSettings:
    """Typed runtime settings loaded from environment."""

    orchestrator_model: str = "databricks-gpt-5-2"
    log_level: str = "INFO"
    log_format: str = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    log_date_format: str = "%Y-%m-%d %H:%M:%S"
    message_bus_backend: str = "structured_logging"
    message_bus_topic: str = "agent-lifecycle-events"
    message_bus_kafka_bootstrap_servers: str = ""
    message_bus_kafka_client_id: str = "multiagent-app"
    message_bus_rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    message_bus_fail_open: bool = True


def get_settings() -> AppSettings:
    """Load backend runtime settings from environment variables."""
    return AppSettings(
        orchestrator_model=os.getenv("ORCHESTRATOR_MODEL", "databricks-gpt-5-2"),
        log_level=os.getenv("BACKEND_LOG_LEVEL", "INFO"),
        log_format=os.getenv(
            "BACKEND_LOG_FORMAT",
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
        ),
        log_date_format=os.getenv("BACKEND_LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S"),
        message_bus_backend=os.getenv("MESSAGE_BUS_BACKEND", "structured_logging"),
        message_bus_topic=os.getenv("MESSAGE_BUS_TOPIC", "agent-lifecycle-events"),
        message_bus_kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", ""),
        message_bus_kafka_client_id=os.getenv("KAFKA_CLIENT_ID", "multiagent-app"),
        message_bus_rabbitmq_url=os.getenv(
            "RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"
        ),
        message_bus_fail_open=os.getenv("MESSAGE_BUS_FAIL_OPEN", "true").lower()
        in {"1", "true", "yes", "on"},
    )
