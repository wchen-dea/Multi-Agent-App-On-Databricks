"""Message bus implementations for agent lifecycle event publishing."""

import json
import logging
from datetime import datetime, timezone
from importlib import import_module
from uuid import uuid4

from backend.services.interfaces import MessageBus
from backend.shared.settings import AppSettings, get_settings

logger = logging.getLogger(__name__)


class NoOpMessageBus:
    """Default no-op message bus used when event emission is not configured."""

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        del event_type, payload


class StructuredLoggingMessageBus:
    """Message bus that publishes events as structured log records."""

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        event = _build_event(event_type, payload)
        logger.info("message_bus_event %s", json.dumps(event, sort_keys=True, default=str))


class KafkaMessageBus:
    """Kafka-backed message bus for production-grade event transport."""

    def __init__(self, bootstrap_servers: str, topic: str, client_id: str) -> None:
        if not bootstrap_servers.strip():
            raise ValueError("KAFKA_BOOTSTRAP_SERVERS must be set when MESSAGE_BUS_BACKEND=kafka")

        try:
            producer_module = import_module("confluent_kafka")
        except Exception as exc:
            raise RuntimeError(
                "Kafka backend requires confluent-kafka. Install with `uv add confluent-kafka`."
            ) from exc

        producer_cls = getattr(producer_module, "Producer")
        self._producer = producer_cls(
            {
                "bootstrap.servers": bootstrap_servers,
                "client.id": client_id,
            }
        )
        self._topic = topic

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        event = _build_event(event_type, payload)
        self._producer.produce(
            self._topic,
            value=json.dumps(event, default=str).encode("utf-8"),
            key=event_type.encode("utf-8"),
        )
        self._producer.poll(0)


class RabbitMQMessageBus:
    """RabbitMQ-backed message bus for lifecycle event transport."""

    def __init__(self, url: str, exchange: str) -> None:
        if not url.strip():
            raise ValueError("RABBITMQ_URL must be set when MESSAGE_BUS_BACKEND=rabbitmq")

        try:
            pika = import_module("pika")
        except Exception as exc:
            raise RuntimeError(
                "RabbitMQ backend requires pika. Install with `uv add pika`."
            ) from exc

        params = pika.URLParameters(url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)

        self._pika = pika
        self._params = params
        self._exchange = exchange
        self._conn = connection
        self._channel = channel

    def _ensure_connection(self) -> None:
        if getattr(self._conn, "is_closed", False):
            self._conn = self._pika.BlockingConnection(self._params)
            self._channel = self._conn.channel()
            self._channel.exchange_declare(
                exchange=self._exchange,
                exchange_type="topic",
                durable=True,
            )

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        self._ensure_connection()
        event = _build_event(event_type, payload)
        self._channel.basic_publish(
            exchange=self._exchange,
            routing_key=event_type,
            body=json.dumps(event, default=str).encode("utf-8"),
            properties=self._pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )

    def close(self) -> None:
        if self._conn and not self._conn.is_closed:
            self._conn.close()


def _build_event(event_type: str, payload: dict[str, object]) -> dict[str, object]:
    """Create a normalized event envelope for all bus backends."""
    return {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "ts": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def default_message_bus(settings: AppSettings | None = None) -> MessageBus:
    """Return a configured message bus implementation for runtime use."""
    cfg = settings or get_settings()
    backend = cfg.message_bus_backend.strip().lower()

    if backend == "noop":
        return NoOpMessageBus()
    if backend == "structured_logging":
        return StructuredLoggingMessageBus()
    if backend == "kafka":
        try:
            return KafkaMessageBus(
                bootstrap_servers=cfg.message_bus_kafka_bootstrap_servers,
                topic=cfg.message_bus_topic,
                client_id=cfg.message_bus_kafka_client_id,
            )
        except Exception:
            if cfg.message_bus_fail_open:
                logger.exception(
                    "Kafka message bus initialization failed; falling back to structured logging"
                )
                return StructuredLoggingMessageBus()
            raise
    if backend == "rabbitmq":
        try:
            return RabbitMQMessageBus(
                url=cfg.message_bus_rabbitmq_url,
                exchange=cfg.message_bus_topic,
            )
        except Exception:
            if cfg.message_bus_fail_open:
                logger.exception(
                    "RabbitMQ message bus initialization failed; falling back to structured logging"
                )
                return StructuredLoggingMessageBus()
            raise

    logger.warning(
        "Unknown MESSAGE_BUS_BACKEND=%r; defaulting to structured logging", cfg.message_bus_backend
    )
    return StructuredLoggingMessageBus()
