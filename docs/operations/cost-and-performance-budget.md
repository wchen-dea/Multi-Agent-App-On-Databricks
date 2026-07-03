# Cost and Performance Budget

Define latency, throughput, and cost constraints for safe operation at scale.

## Purpose

Create measurable operating budgets and escalation thresholds for runtime cost and performance.

## Performance Targets

- Interactive response target: optimized for streaming-first UX
- Preflight startup target: server readiness and invocation checks must pass in local validation
- Tool route health: MCP/tool failures should degrade gracefully when possible

## Cost Drivers

- LLM token usage for orchestrator and tool calls
- External serving endpoint invocations
- Message bus backend transport and persistence costs
- Evaluation simulation and scorer usage in CI

## Budget Controls

- Use route selection discipline to avoid unnecessary tool fan-out.
- Keep policy denials and retries visible via lifecycle metrics.
- Tune evaluation suite size by release tier.
- Apply fallback behavior for unavailable non-critical transports.

## Monitoring Signals

- Request success/failure rate
- Tool invocation count and failure ratio
- Guardrail block ratio
- Evaluation pass/fail trend

## Release Checks

- Verify KPI gates before deployment.
- Review performance and error trends after deployment.

## Related Documents

- ../quality/evaluation-spec.md
- runbook.md
- ../architecture/system-architecture.md
