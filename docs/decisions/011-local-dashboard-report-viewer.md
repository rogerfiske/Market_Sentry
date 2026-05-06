# Decision 011: Local Dashboard and Report Viewer

## Status

Accepted

## Date

2026-05-06

## Context

Milestones 1-11 built the complete data pipeline: candidate discovery, review, scoring, monitoring, cross-site enrichment, county verification, Effective DOM v2, workflow orchestration, and report generation. All output was CLI-based or CSV-based.

Users needed to open CSV files in spreadsheet editors to review candidates, compare Effective DOM v1/v2, check county verification status, and review cross-site discrepancies. This was functional but friction-heavy for day-to-day use.

## Decision

### 1. Add a local dashboard before live retrieval

A local Streamlit dashboard was added as Milestone 12 to provide a browser-based review interface. This was prioritized before live data retrieval because:

- The existing pipeline generates multiple report types that are difficult to cross-reference in CSV format.
- A dashboard makes the review workflow more accessible without changing the data pipeline.
- It validates that the data model supports interactive review before adding network complexity.

### 2. Dashboard reads only local data

The dashboard reads exclusively from:

- Local SQLite database (`db/marketsentry.db`)
- Local CSV reports in `data/exports/`
- Local report manifest (`data/exports/report_manifest.csv`)
- Local workflow summary markdown files

No network calls, API requests, or external data fetching is performed. This preserves the local-first design principle.

### 3. Streamlit was chosen over static HTML

Streamlit was selected because:

- It provides interactive filtering (sidebar sliders, dropdowns) without custom JavaScript.
- It renders pandas DataFrames natively, which the codebase already uses.
- It runs locally with a single command (`streamlit run ...`).
- It does not require Streamlit Cloud, secrets, or external APIs.
- The dependency is well-maintained and compatible with the existing Python stack.

Static HTML was considered but rejected because:

- It would require manual page regeneration after each data change.
- Interactive filtering would need custom JavaScript development.
- The user would need to remember to regenerate the HTML after each workflow run.

### 4. Dashboard is a review tool, not a recommendation engine

The dashboard displays analytical data for human review. It does not:

- Make purchase recommendations.
- Infer seller intent.
- Score or rank properties beyond what the existing scoring module provides.
- Add new metrics or calculations.

Language throughout the dashboard is neutral and analytical.

## Consequences

### Positive

- Users can review all data in a single browser interface.
- Interactive filtering makes it easy to focus on specific candidate subsets.
- The dashboard validates the data model for interactive review.
- No network calls or external dependencies beyond Streamlit.

### Negative

- Adds Streamlit as a dependency. Acceptable given its stability and the interactive benefits.
- Dashboard is limited to the data already in the database/CSV reports.

### Neutral

- Existing CLI commands remain available for users who prefer terminal-based workflows.
- No schema changes required.
- No changes to the data pipeline or scoring logic.
