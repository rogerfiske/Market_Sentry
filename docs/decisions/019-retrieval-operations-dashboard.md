# Decision 019: Retrieval Operations Dashboard

**Date:** 2026-05-07
**Status:** Accepted
**Milestone:** 20

## Context

Milestones 14-19 established compliance-aware retrieval with policy enforcement, fixture-first HTTP retrieval for Redfin, a processing pipeline, a batch orchestrator, and a two-step approval workflow. These milestones produce audit logs, manifests, fixture files, and queue records that operators need to review. Milestone 20 adds read-only visibility into the retrieval ecosystem through the existing dashboard and CLI.

## Decisions

### Why Retrieval Operations Visibility Is Added Before Expanding Sources

Operational visibility should precede capability expansion because:

1. Operators need to verify the existing Redfin retrieval workflow works correctly before adding new sources.
2. Audit logs and manifests accumulate without a consolidated view, making it harder to detect issues.
3. A dashboard makes policy decisions, blocked reasons, and fixture status visible at a glance.
4. Adding visibility first reduces the risk of operator mistakes when retrieval is expanded later.
5. The dashboard provides a verification step: if the Redfin workflow looks correct, expanding to other sources is lower risk.

### Why the Dashboard Is Read-Only for Retrieval Operations

The retrieval operations dashboard is read-only because:

1. Retrieval actions (prepare, approve, retrieve) require explicit CLI invocation with flags like `--force-live`.
2. A dashboard "retrieve" button would bypass the human-in-the-loop approval workflow.
3. Read-only visibility provides value without introducing new risk.
4. The dashboard is a monitoring/observation tool, not an action trigger.
5. Operators can review the dashboard and then decide whether to run CLI commands.

### Why Live Retrieval Remains Manually Invoked Only

Live retrieval is not automated because:

1. Each retrieval makes a network call to an external site.
2. Automated retrieval could exceed rate limits or violate terms of service.
3. The human-in-the-loop principle requires conscious retrieval decisions.
4. Manual invocation ensures the operator monitors the process.
5. Scheduled tasks remain local-only by design.

### How Visibility Reduces Operator Mistakes

The dashboard and CLI summary reduce mistakes by:

1. Showing capture queue status so the operator knows what needs attention.
2. Showing approval package history so the operator knows what was approved and retrieved.
3. Showing blocked reasons so the operator can fix configuration issues.
4. Showing safety configuration so the operator can verify settings before retrieval.
5. Showing audit records so the operator can verify compliance.

## Consequences

- A "Retrieval Operations" section is added to the existing Streamlit dashboard.
- A `retrieval-operations-summary` CLI command provides ASCII-safe text output.
- An `export-retrieval-operations-report` CLI command exports reports as Markdown or CSV.
- All operations are read-only; no retrieval actions are triggered from the dashboard.
- The dashboard loads data from local files (SQLite, CSV manifests, audit logs, fixture directories).
- No network calls are performed by any dashboard function.
- No scheduled task invokes live retrieval or approved retrieval.
