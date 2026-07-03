# Documentation Index

Use this index to navigate project documentation by purpose:

- [business-specs.md](business-specs.md): business goals, requirements, constraints, and success metrics.
- [technical-specs.md](technical-specs.md): centralized technical domain map and ownership boundaries.
- [architecture.md](architecture.md): high-level system architecture, boundaries, and request flow.
- [design.md](design.md): low-level implementation details, runtime behavior, and configuration model.
- [runbook.md](runbook.md): deployment and operations procedures.
- [claude.md](claude.md): unified Claude skill summary, usage order, and operating guidelines.
- [adrs/README.md](adrs/README.md): architecture decision records and long-lived technical decisions.

## Recommended Read Order

1. [architecture.md](architecture.md)
2. [business-specs.md](business-specs.md)
3. [technical-specs.md](technical-specs.md)
4. [design.md](design.md)
5. [runbook.md](runbook.md)
6. [claude.md](claude.md)
7. [adrs/README.md](adrs/README.md)

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

### Unity Catalog Audit Table

```bash
MESSAGE_BUS_BACKEND=uc_table
MESSAGE_BUS_TOPIC=agent-lifecycle-events
MESSAGE_BUS_FAIL_OPEN=true
UC_AUDIT_WAREHOUSE_ID=<warehouse-id>
UC_AUDIT_CATALOG=main
UC_AUDIT_SCHEMA=observability
UC_AUDIT_TABLE=agent_lifecycle_events
```

For deployment and incident procedures, see [runbook.md](runbook.md).
