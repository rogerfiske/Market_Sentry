# Decision 010: End-to-End Operating Workflow

## Status

Accepted

## Date

2026-05-05

## Context

Milestones 1-10 built individual modules for candidate discovery, review, scoring, monitoring, cross-site enrichment, county verification, and Effective DOM v2 persistence. Each module had its own CLI command, but there was no single orchestrated workflow tying the full pipeline together.

Users had to know the correct order of CLI commands, remember which directories to pass, and manually ensure each step succeeded before running the next one. This created friction and made it easy to skip steps or run them in the wrong order.

## Decision

### 1. Add workflow orchestration before live retrieval

Milestone 11 adds three orchestrated workflows that combine existing modules into coherent sequences:

- **run_initial_review_workflow**: Prepares new candidates for human review (import, parse, enrich, recalculate, export review CSV).
- **run_watchlist_refresh_workflow**: Refreshes watched properties with available local data (enrich, cross-site, county, v2, snapshot, reports).
- **run_full_fixture_demo_workflow**: Runs a deterministic demo with sample data (seed, review, promote, snapshot, all reports).

These workflows call existing module functions. They do not duplicate business logic.

### 2. Workflows use manual inputs and saved fixtures

All workflows operate on locally saved HTML fixtures and CSV imports. No live scraping, browser automation, or network calls are made. This is intentional:

- Ensures reproducibility.
- Avoids rate-limiting or bot-detection issues.
- Keeps the user in control of what data enters the system.
- Prepares the orchestration layer for future live retrieval milestones.

### 3. Report manifests help auditability

Each workflow run appends entries to `data/exports/report_manifest.csv`. This provides:

- A chronological record of all reports generated.
- The workflow that produced each report.
- Row counts for each report.
- Timestamps for each generation.

This supports auditability without adding database complexity.

### 4. Workflow summaries provide operational visibility

Each workflow generates a markdown summary at `data/exports/workflow_summary_YYYYMMDD_HHMMSS.md` containing:

- Step-by-step results with status, counts, and duration.
- Warnings and errors.
- Output files with row counts.
- Next recommended user action.

This reduces the need to scroll through CLI output to understand what happened.

### 5. Typed result models ensure structured output

WorkflowStepResult and WorkflowRunResult Pydantic models provide structured, typed workflow output. This enables:

- Programmatic inspection of workflow results.
- Consistent step tracking across all workflows.
- Future integration with dashboards or notifications.

## Consequences

### Positive

- Users can run the full pipeline with a single command.
- Step ordering is handled by the orchestration layer.
- Failures are captured and reported without stopping the entire workflow.
- Report manifest provides an audit trail.
- Workflow summaries provide actionable next steps.
- Demo workflow enables testing without real data.

### Negative

- Adding workflow orchestration increases the module count. Acceptable for operational usability.
- Workflows may mask individual step failures if users only check the final summary. Mitigated by explicit error reporting in summaries.

### Neutral

- Existing individual CLI commands remain available for users who prefer granular control.
- No schema changes required for this milestone.
- No live network calls or scraping added.
- All existing Milestone 1-10 tests continue to pass.

## Alternatives Considered

1. **Shell scripts**: Write bash/PowerShell scripts to chain CLI commands. Rejected because scripts lack error handling, typed results, and cross-platform consistency.

2. **Makefile targets**: Use make targets for workflow steps. Rejected because it adds a build system dependency and lacks structured result reporting.

3. **Add live retrieval first**: Implement live scraping before orchestration. Rejected because orchestration should be validated with fixture data before adding network complexity.
