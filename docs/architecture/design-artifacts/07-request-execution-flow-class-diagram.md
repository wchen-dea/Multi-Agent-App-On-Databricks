# Request Execution Flow: Class Diagram (Simplified)

These diagrams focus on request execution in `src/backend/api/handlers.py` after the staged-pipeline refactor.
They separate the invoke and stream pipeline views while preserving the shared contract context.

## Invoke Pipeline

```mermaid
classDiagram
direction LR

class ResponsesAgentRequest
class ResponsesAgentResponse
class AsyncExitStack

class RequestStage {
  +request: ResponsesAgentRequest
  +runtime_auth
  +messages: list
}

class ConnectedStage {
  +runtime_auth
  +unavailable: list[str]
  +agent
}

class InvokeFinalizedStage {
  +output_items: list[dict]
  +unavailable: list[str]
}

class HandlerDependencies {
  +runtime_auth_builder
  +mcp_connector
  +orchestrator_factory
  +guardrails_evaluator
  +message_bus
}

class InvokePipeline {
  +_prepare_request_stage(request)
  +_connect_request_stage(stack, prepared)
  +_execute_invoke_stage(connected, messages)
  +_finalize_invoke_stage(result, connected)
}

class Guardrails {
  +_guardrail_scope_subagents(payloads, subagents)
  +_governed_source_suffix_with_fallback(payloads, subagents)
}

HandlerDependencies ..> InvokePipeline : drives

InvokePipeline ..> RequestStage : prepare
InvokePipeline ..> ConnectedStage : connect
InvokePipeline ..> InvokeFinalizedStage : finalize
InvokePipeline --> ResponsesAgentResponse : returns

InvokePipeline ..> Guardrails : evaluate

RequestStage --> ResponsesAgentRequest
InvokePipeline ..> AsyncExitStack : context scope
```

## Stream Pipeline

```mermaid
classDiagram
direction LR

class ResponsesAgentRequest
class ResponsesAgentStreamEvent
class AsyncExitStack

class RequestStage {
  +request: ResponsesAgentRequest
  +runtime_auth
  +messages: list
}

class ConnectedStage {
  +runtime_auth
  +unavailable: list[str]
  +agent
}

class StreamExecutedStage {
  +event_count: int
  +buffered_events: list
  +buffered_payloads: list[dict]
  +streamed_text_parts: list[str]
}

class StreamFinalizedStage {
  +event_count: int
  +buffered_events: list
  +source_suffix: str
  +unavailable: list[str]
  +guardrail_blocked: bool
  +guardrail_reasons: tuple[str]
}

class HandlerDependencies {
  +runtime_auth_builder
  +mcp_connector
  +orchestrator_factory
  +guardrails_evaluator
  +message_bus
}

class StreamPipeline {
  +_prepare_request_stage(request)
  +_connect_request_stage(stack, prepared)
  +_execute_stream_stage(connected, messages)
  +_finalize_stream_stage(executed, connected)
}

class Guardrails {
  +_guardrail_scope_subagents(payloads, subagents)
  +_governed_source_suffix_with_fallback(payloads, subagents)
}

HandlerDependencies ..> StreamPipeline : drives

StreamPipeline ..> RequestStage : prepare
StreamPipeline ..> ConnectedStage : connect
StreamPipeline ..> StreamExecutedStage : execute
StreamPipeline ..> StreamFinalizedStage : finalize
StreamPipeline --> ResponsesAgentStreamEvent : yields

StreamPipeline ..> Guardrails : evaluate

RequestStage --> ResponsesAgentRequest
StreamPipeline ..> AsyncExitStack : context scope
```

## Notes

- Shared stages (`prepare`, `connect`) enforce a common pipeline contract for invoke and stream.
- Stream path buffers events, applies guardrails, then emits buffered events (plus optional source suffix event).
- Guardrail block behavior diverges by mode:
  - invoke: raises `UserError`
  - stream: emits block delta and terminates stream
