# Concept Phase: Detailed Diagrams

This document captures detailed concept artifacts that shape implementation boundaries and governance assumptions.

## 1. Product Scope Map

```mermaid
flowchart LR
    subgraph InScope[In Scope]
        S1[Multi-agent orchestration]
        S2[Policy and guardrails]
        S3[Audit event lifecycle]
        S4[Release quality gate]
    end

    subgraph OutScope[Out of Scope]
        O1[Custom BI dashboarding]
        O2[Long-running agent mailbox workflows]
        O3[Cross-tenant orchestration]
    end
```

## 2. Trust Boundary and Risk Sketch

```mermaid
flowchart TB
    subgraph Zone1[User Zone]
        U[User Session]
    end

    subgraph Zone2[App Runtime Zone]
        UI[Frontend]
        ORCH[Orchestrator]
        POL[Policy and Guardrails]
    end

    subgraph Zone3[Enterprise Services Zone]
        TOOL[Tools and MCP]
        DATA[Governed Data Assets]
    end

    subgraph Zone4[Control Zone]
        AUDIT[Audit Sink]
        SEC[Security Monitoring]
    end

    U --> UI --> ORCH --> TOOL --> DATA
    ORCH --> POL
    ORCH --> AUDIT
    POL --> AUDIT
    AUDIT --> SEC

    R1[Risk: prompt injection] -.mitigate.-> POL
    R2[Risk: unauthorized access] -.mitigate.-> ORCH
    R3[Risk: untraceable output] -.mitigate.-> AUDIT
```
