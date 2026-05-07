# Decision 020: Retrieval Health Checks

## Status

Accepted

## Context

Milestones 14-20 built a retrieval ecosystem with compliance enforcement, fixture capture queue, live HTTP retrieval, processing pipeline, batch orchestration, approval workflow, and operations dashboard. The operator needs automated guidance on stale items, missing configuration, audit anomalies, and next actions.

## Decision

Add retrieval operations aging, alerts, and health checks as a read-only observability layer (Milestone 21).

## Why health checks are added before expanding sources

Before adding new live sources (Zillow, Realtor, County, etc.), the operator needs visibility into the health of the existing Redfin retrieval pipeline. Health checks ensure that stale items, missing config, and anomalies are surfaced before scaling retrieval to additional sources. Expanding sources without operational monitoring would increase risk of unnoticed failures.

## Why stale approvals are flagged

Approval packages are time-sensitive. Policy checks are re-evaluated at retrieval time, and dry-run approvals expire after 24 hours. A stale approval CSV with unretrieved approved rows indicates the operator may have forgotten to run the retrieval step, or policy conditions may have changed. Flagging stale approvals prevents wasted effort and ensures the operator re-evaluates before proceeding.

## Why network_call_performed=true records are highlighted

The system is designed so that network calls only occur during explicit live retrieval commands with --force-live. Any audit record with network_call_performed=true outside of expected retrieval operations is an anomaly that warrants investigation. Highlighting these as critical ensures the operator reviews all actual network calls for compliance.

## Why dashboard remains read-only

The dashboard displays health check results but does not offer mutation actions (e.g., "skip this capture request" or "discard this approval package"). Write actions require CLI commands with explicit user intent. This prevents accidental state changes from the dashboard and maintains the human-in-the-loop principle.

## Severity Levels

- **info**: Informational, no action needed
- **warning**: Stale items or minor config gaps
- **error**: Missing required config when live retrieval is enabled
- **critical**: Unexpected network calls in audit logs

## Consequences

- Operators get automated health guidance without manual log inspection
- Stale items are surfaced before they accumulate
- Missing config is caught early
- Audit anomalies are flagged for immediate review
- Dashboard remains safe for passive monitoring
