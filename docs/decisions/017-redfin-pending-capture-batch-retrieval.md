# Decision 017: Redfin Pending Capture Batch Retrieval

**Date:** 2026-05-07
**Status:** Accepted
**Milestone:** 18

## Context

Milestones 14-17 established compliance-aware retrieval with policy enforcement, fixture-first HTTP retrieval for Redfin, and a processing pipeline connecting retrieved fixtures to candidate discovery and enrichment. The fixture capture queue (Milestone 15) tracks URLs that need fixture capture. Milestone 18 adds a controlled batch orchestrator that processes pending Redfin capture queue items with full policy enforcement.

## Decisions

### Why Batch Retrieval Operates on Capture Queue Items Only

The batch orchestrator processes only pending fixture capture queue items rather than arbitrary URLs. This design:

1. Integrates naturally with the existing capture queue workflow.
2. Ensures only URLs that were previously identified as needing data are retrieved.
3. Provides built-in deduplication (the queue deduplicates by URL).
4. Allows tracking from queue request through retrieval to processing.
5. Prevents ad-hoc mass retrieval of arbitrary URLs.

### Why Default Is Dry-Run

The batch orchestrator defaults to dry-run mode because:

1. Dry-run evaluates policy checks without any network calls.
2. It lets the user preview what would happen before committing.
3. It follows the established pattern from Milestones 14-16.
4. It prevents accidental live retrieval.
5. The `--force-live` flag ensures a conscious opt-in decision.

### Why Scheduled Tasks Do Not Invoke Live Retrieval

Scheduled tasks remain local-only because:

1. Unattended live retrieval lacks human oversight.
2. Rate limit enforcement is harder to guarantee across scheduled runs.
3. Network failures in scheduled tasks are harder to diagnose.
4. The human-in-the-loop principle requires conscious retrieval decisions.
5. Manual fixture capture remains the recommended default workflow.

### Why Retrieved HTML Remains Fixture-First

Retrieved pages are saved as local HTML fixtures rather than parsed directly because:

1. The original HTML is preserved for review and reprocessing.
2. Parsing and retrieval are independent operations.
3. A failed parse does not lose the retrieved data.
4. The same parsers work for both manual and live-retrieved fixtures.
5. The processing manifest provides idempotent reprocessing.

### Why Other Sources Are Deferred

Batch retrieval is limited to Redfin because:

1. Redfin is the primary candidate discovery source with mature parsers.
2. Other sources (Zillow, Realtor, etc.) lack equivalent retrieval and parsing infrastructure.
3. Each source requires its own compliance review, robots policy, and adapter.
4. Starting with one source validates the batch pattern before extending to others.

## Consequences

- Batch retrieval is available for Redfin only, defaulting to dry-run mode.
- Users must explicitly use `--force-live` for any network calls.
- The full policy enforcement pipeline is applied per item in the batch.
- Successful retrievals are saved as fixtures, optionally processed, and queue items marked captured.
- Blocked items remain pending with clear reasons.
- Batch and per-item manifests provide audit trails.
- No scheduled task invokes live retrieval.
