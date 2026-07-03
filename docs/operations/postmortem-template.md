# Postmortem Template

Use this template for production incidents, major regressions, or release-gate failures.

## Incident Summary

- Title:
- Date and time window:
- Severity:
- Impacted environments:
- Reported by:

## Customer and Business Impact

- Who was impacted:
- What behavior failed:
- Duration:
- Business effect:

## Timeline (UTC)

1. Detection
2. Initial triage
3. Mitigation
4. Recovery
5. Follow-up completion

## Root Cause

- Technical root cause:
- Contributing factors:
- Why safeguards did not prevent this:

## Detection and Response

- How detected:
- Which alerts or checks fired:
- What worked:
- What delayed recovery:

## Policy, Safety, and Audit Notes

- Were policy checks involved:
- Were guardrails involved:
- Were lifecycle/audit events complete:

## Corrective Actions

1. Code fixes
2. Test coverage additions
3. Eval suite updates
4. Runbook/process updates

For each action:

- Owner:
- Due date:
- Status:

## Prevention Plan

- Release gate or threshold changes:
- Additional monitoring:
- Architectural adjustments:

## References

- PR/commit:
- Dashboard links:
- Log and trace references:
- Related ADRs:
