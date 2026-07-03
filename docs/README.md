# Documentation Index

Documentation in `docs/` is organized by purpose:

- [docs/architecture.md](architecture.md): high-level system architecture, boundaries, and request flow.
- [docs/design.md](design.md): low-level implementation details, runtime behavior, and configuration model.
- [docs/runbook.md](runbook.md): deployment and operations procedures.
- [docs/claude.md](claude.md): unified Claude skill summary, usage order, and operating guidelines.

## Recommended Read Order

1. [docs/architecture.md](architecture.md)
2. [docs/design.md](design.md)
3. [docs/runbook.md](runbook.md)
4. [docs/claude.md](claude.md)

## Quick Config Snippets

Use these in `.env` for local message-bus transport selection.

### Structured Logging (default)

```bash
MESSAGE_BUS_BACKEND=structured_logging
MESSAGE_BUS_TOPIC=agent-lifecycle-events
MESSAGE_BUS_FAIL_OPEN=true
```

### Kafka

```bash
MESSAGE_BUS_BACKEND=kafka
MESSAGE_BUS_TOPIC=agent-lifecycle-events
MESSAGE_BUS_FAIL_OPEN=true
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CLIENT_ID=multiagent-app
```

### RabbitMQ

```bash
MESSAGE_BUS_BACKEND=rabbitmq
MESSAGE_BUS_TOPIC=agent-lifecycle-events
MESSAGE_BUS_FAIL_OPEN=true
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

For full operational guidance, see [docs/runbook.md](runbook.md).
