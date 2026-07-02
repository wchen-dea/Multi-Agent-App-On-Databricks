# Multiagent App on Databricks: Architecture (High Level)

## Purpose

Describe the high-level system shape, major boundaries, and end-to-end request flow.

## Scope

This document covers high-level architecture only. Implementation-level details are in `docs/design.md`, and operational procedures are in `docs/runbook.md`.

## Current Status (2026-07-01)

- Dev deployment is live with Chainlit enabled.
- Hosted runtime uses `uv run start-app`.
- Deployments may intermittently fail when Terraform provider registry is unreachable; direct app deploy is the operational fallback.

## Main Content

### Overview

This project is an MVP multi-agent orchestrator deployed on Databricks Apps.
It routes user requests to one or more backend capabilities:

- Genie space tools (via MCP)
- Serving endpoint agents
- Optional app-based specialists

Runtime stack:

- MLflow Agent Server
- OpenAI Agents SDK
- Databricks OpenAI-compatible runtime clients

### Major Components

- Client: Chainlit UI
- Entry runtime: MLflow Agent Server (`ResponsesAgent`)
- Orchestration layer: tool selection and response composition
- Integration layer: MCP + serving endpoint calls
- Data and semantic layer: Genie space, enterprise data assets

### Deployment Diagram

```mermaid
flowchart LR
    subgraph Personas[Personas]
        P1[Business User]
        P2[Analyst]
        P3[Operator]
    end

    subgraph Client[Client UI]
        UI[Chainlit UI]
    end

    subgraph Platform[Databricks App Platform]
        AS[MLflow Agent Server ResponsesAgent]
        ORCH[Agent Orchestration Service]
        MCP[MCP Integration Layer]
        LLM[Databricks-Provided LLM]

        subgraph Agents[Multiple Agents]
            A1[Genie Sales Agent]
            A2[Serving Endpoint Agent Knowledge Assistant]
            A3[Serving Endpoint Agent Lakebase Vector Storage]
        end

        subgraph Semantic[Business Semantic Layer]
            BSL[Genie Space / Semantic Model]
        end
    end

    subgraph Data[Enterprise Data]
        KB[Knowledge Base]
        FS[Feature Stores]
        RDS[Relational Data Store]
    end

    P1 --> UI
    P2 --> UI
    P3 --> UI

    UI --> AS
    AS --> ORCH
    ORCH --> A1
    ORCH --> A2
    ORCH --> A3

    A1 --> LLM
    A2 --> LLM
    A3 --> LLM
    ORCH --> LLM

    ORCH --> MCP
    MCP --> BSL
    BSL --> KB
    BSL --> FS
    BSL --> RDS

    A1 --> MCP
    A2 --> MCP
    A3 --> MCP
```

### Request Flow

```mermaid
flowchart TD
    U[User]
    U --> UI[Chainlit UI]
    UI --> APP[Databricks App Endpoint]
    APP --> S[MLflow Agent Server ResponsesAgent]
    S --> H[invoke_handler / stream_handler]
    H --> O[Orchestrator Agent]

    O --> G[Genie Sales Agent via MCP]
    O --> K[Serving Endpoint Agent knowledge assistant]
    O --> L[Serving Endpoint Agent lakebase vector storage]

    G --> M[MCP Genie Space]
    K --> R1[Model Serving Responses API]
    L --> R1

    M --> R[Response Aggregation]
    R1 --> R
    R --> UI
    UI --> U
```

### Environment Topology

| Environment | Target | Mode | Profile |
| ---- | ---- | ---- | ---- |
| Development | dev | development | dev |
| QA | qa | development | qa |
| Staging | stg | production | stg |
| Production | prod | production | prd |

## Related Docs

- `docs/design.md`: low-level implementation details
- `docs/runbook.md`: operations and incident handling
