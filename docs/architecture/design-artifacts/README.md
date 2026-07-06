# AI System Design Artifacts (Centralized)

This folder centralizes the full system-design artifact set for the AI platform across concept, logical, and deployment phases.

## Scope

The artifact set is organized by phase and depth:

- Concept phase: business and system framing
- Logical phase: software architecture and runtime behavior
- Deployment phase: runtime topology and operations

For each phase, artifacts are split into:

- High level: executive and architecture-overview view
- Detailed: engineering implementation and operations view

## Artifact Inventory

1. [00-architecture-board-review.md](00-architecture-board-review.md)
2. [01-concept-high-level.md](01-concept-high-level.md)
3. [02-concept-detailed.md](02-concept-detailed.md)
4. [03-logical-high-level.md](03-logical-high-level.md)
5. [04-logical-detailed.md](04-logical-detailed.md)
6. [05-deployment-high-level.md](05-deployment-high-level.md)
7. [06-deployment-detailed.md](06-deployment-detailed.md)
8. [07-request-execution-flow-class-diagram.md](07-request-execution-flow-class-diagram.md)
9. [08-backend-class-diagram-as-is.md](08-backend-class-diagram-as-is.md)

## Coverage Matrix

| Phase | High Level | Detailed |
| --- | --- | --- |
| Concept | System context, actor map, value flow, capability map | scope map, trust boundary and risk sketch |
| Logical | container map, request flow, data lineage, auth flow | component map, orchestration sequence, policy and prompt layering, failure and recovery, session state, evaluation gate |
| Deployment | environment topology, runtime deployment map | network topology, CI/CD and promotion, observability, HA and DR |

## How to Use

1. Start with concept high-level for business and platform framing.
2. Move to logical high-level and detailed for architecture and runtime behavior.
3. Use deployment high-level and detailed for release planning and operations.

## Ownership and Update Policy

- Primary owner: platform engineering
- Review partners: product, security/governance, operations
- Update triggers:
  - new integration, model, or tool route
  - auth or policy changes
  - deployment topology or CI/CD changes
  - observability or incident-response changes

Update these artifacts in the same change where behavior changes.
