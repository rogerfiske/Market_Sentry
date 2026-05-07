# Decision 018: Redfin Retrieval Approval Workflow

**Date:** 2026-05-07
**Status:** Accepted
**Milestone:** 19

## Context

Milestones 14-18 established compliance-aware retrieval with policy enforcement, fixture-first HTTP retrieval for Redfin, a processing pipeline, and a batch orchestrator for pending capture queue items. Milestone 18's batch retrieval processes all pending items at once with `--force-live`. Milestone 19 adds a two-step approval workflow that requires explicit per-item user approval before batch live retrieval.

## Decisions

### Why User Approval Is Required Before Batch Live Retrieval

Batch retrieval processes multiple URLs in sequence. Without per-item approval:

1. A large capture queue could trigger many requests at once.
2. The operator may not have reviewed each URL's policy status.
3. There is no record of which items the operator intended to retrieve.
4. Accidental batch runs could retrieve unintended URLs.

The approval workflow requires the operator to review each item and explicitly set `approved_for_live=true`, providing intent documentation and preventing accidental mass retrieval.

### Why approved_for_live Defaults to False

The `approved_for_live` column defaults to `false` for every row because:

1. No item should be retrieved without explicit user action.
2. The default-false pattern prevents copy-paste or template errors from approving items.
3. Each `true` value represents a conscious decision by the operator.
4. This follows the principle of least privilege for network operations.
5. The user must actively edit the CSV to opt in, not opt out.

### Why Policy Checks Are Rerun at Retrieval Time

Policy checks from the dry-run phase may become stale:

1. Robots policy files may have been updated.
2. Rate limit windows may have shifted.
3. Compliance configuration may have changed.
4. Dry-run approvals may have expired.
5. The capture queue item may have been captured by another workflow.

Rerunning all policy checks at retrieval time ensures that the retrieval decision reflects current system state, not the state at preparation time. An approved item that now fails policy checks is blocked.

### Why URL and Capture Request Validation Is Required

The approval CSV references capture queue items by ID and URL:

1. A capture request may have been captured, skipped, or archived between preparation and retrieval.
2. The URL in the approval CSV must match the current queue item's URL.
3. This prevents retrieval of stale or modified requests.
4. URL validation ensures the operator is retrieving what they reviewed.
5. Capture request validation ensures the queue state is consistent.

### Why Scheduled Tasks Do Not Run Approved Retrieval

Scheduled tasks remain local-only because:

1. Approved retrieval still makes network calls when `--force-live` is used.
2. Unattended approved retrieval lacks human oversight at execution time.
3. The approval step only documents intent; it does not substitute for execution-time oversight.
4. The human-in-the-loop principle applies at both approval and retrieval time.
5. Manual execution ensures the operator monitors the retrieval process.

## Consequences

- A two-step approval workflow is available: prepare, then retrieve.
- Operators must edit the approval CSV to approve items before retrieval.
- `approved_for_live` defaults to `false` for every item.
- `--force-live` is still required at retrieval time.
- All Milestone 14-18 policy checks are rerun at retrieval time.
- URL and capture request validation prevent stale approvals.
- The approval manifest provides an audit trail.
- No scheduled task invokes approved retrieval.
- Manual fixture capture remains available as an alternative.
