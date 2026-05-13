# Decision 046: Local Email Digest Draft

## Date

2026-05-13

## Status

Accepted

## Context

Milestone 46 established local alert highlight preferences and focus views. Operators could configure which alert categories to emphasize and generate focused digest reports. The next step was to provide a way to render focused items into a shareable email-style format without introducing outbound notification infrastructure.

## Decisions

### Why local draft follows focus preferences

The email digest draft reads focused items produced by the Milestone 46 focus preference system. This ensures that the email content reflects the same filtering, sorting, and emphasis that operators see in the dashboard and focus digest reports. Operators control what appears in the email draft through the same preference config they already use.

### Why no outbound notification is sent

Outbound email, SMS, webhook, and other notification channels are explicitly excluded. The email digest is designed as a local file export that operators manually review and optionally copy/paste into their own email client. This avoids dependencies on external services, credential management, and delivery infrastructure. Future milestones may add optional notification channels, but the current design prioritizes local-first operation.

### Why no credentials are stored

The module does not request, store, or read email addresses, passwords, API keys, or authentication tokens. There is no SMTP configuration, no Gmail API setup, and no Outlook automation. This eliminates credential management complexity and security concerns.

### Why scheduled script is local/report-only

The `run_portfolio_review_pack_report.bat` script includes `export-portfolio-alert-email-digest` as a report command. It exports local files only and does not send email, perform live retrieval, run mutation commands, or invoke outbound notification services. The script remains safe for unattended scheduled execution.

### Why candidate/watchlist/alert state is not automatically changed

The email digest draft is a read-only rendering of existing focus items. It does not triage, archive, expire, promote, or otherwise modify candidate, watchlist, or alert records. Operators use existing triage and archive workflows to take actions after reviewing the draft.

### Why Quiet Score gatekeeper is unchanged

The email digest module does not modify Quiet Score gatekeeper logic, thresholds, or scoring. The quiet gatekeeper threshold remains at 70.0. The digest only reads and renders existing alert data.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. The email digest module does not reference walkability metrics or include walkability fields in any output.

## Consequences

- Operators can generate email-style digest drafts from focused alert items as local files
- Plain-text, Markdown, and optional .eml formats are supported
- Every draft includes a safety note stating it is a local draft only, not sent
- Manual copy/paste instructions guide operators through sharing the content
- The dashboard shows a Portfolio Alert Email Draft subsection with preview and metadata
- The scheduled script includes email digest export as a local-only report command
- No outbound notifications are sent
- No credentials are stored or requested
- No candidates, watchlist entries, or alert statuses are modified
- All existing alert, trend, review pack, comparison, digest, triage, archive, expiration, lifecycle, health, configurable rule, alert history, and focus preference workflows continue unchanged
