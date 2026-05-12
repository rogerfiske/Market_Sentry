# Decision 037: Watchlist Operations Digest

## Date

2026-05-12

## Status

Accepted

## Context

Milestones 27-37 added numerous reporting and analysis features: cross-site analytics, alert triage, hygiene checks, lifecycle audits, health scoring, and health trends. Operators must run multiple CLI commands and review multiple reports to understand the overall state of the watchlist. A consolidated digest view is needed to provide a single entry point for operational status.

## Decisions

### Why the digest consolidates all local reports

The digest scans the database and existing export files to build a unified summary across seven operational areas: candidate review, watchlist status, Effective DOM/churn, cross-site validation, alerts/hygiene, lifecycle health, and retrieval operations. This eliminates the need to run separate commands for each area.

### Why the digest is entirely read-only

The digest is a reporting tool. It queries database tables using SELECT statements only and reads existing export files. It does not INSERT, UPDATE, or DELETE any database rows. The only file writes are the digest export files themselves (CSV and Markdown).

### Why priority ranking is included

Operators need to know which properties require attention first. The ranking scores properties based on lifecycle health labels, open high/critical alerts, stale alerts, and churn indicators. Priority labels (immediate_review, high_review, normal_review, monitor) give operators a quick way to prioritize their review time.

### Why next actions are generated

Recommended next actions translate digest metrics into specific CLI commands. When the digest detects pending candidate decisions, stale alerts, or attention-required health scores, it suggests the appropriate command. This reduces the operator's need to remember which command handles which situation.

### Why the scheduled script is local and report-only

The `run_operations_digest_report.bat` script runs the digest export only. It does not invoke live retrieval, alert mutation, or watchlist status changes. This keeps the scheduled automation safe for unattended execution.

### Why watchlist state is not automatically changed

The operations digest observes and reports. It does not modify candidate decisions, alert statuses, watchlist fields, or property data. Operators use the existing triage, archive, and expiration workflows to take actions based on digest observations.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper evaluates property stability based on listing history and churn patterns. The operations digest does not reference or modify Quiet Score or Vibrancy Score.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields, parsing, or scoring have been added in any milestone, including this one.

## Consequences

- Operators get a single-command view of all operational metrics.
- Priority ranking highlights which properties need review first.
- Next actions suggest specific commands to resolve identified issues.
- CSV and Markdown exports enable offline review and sharing.
- Dashboard integration provides interactive digest exploration.
- The scheduled script enables automated local reporting.
- No alerts, candidates, or watchlist entries are modified by digest operations.
- All existing triage, archive, expiration, lifecycle, and health workflows continue unchanged.
