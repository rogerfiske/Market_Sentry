# Claude Code Prompt 047 - Local Email Digest Draft Export for Portfolio Focus Alerts

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: 353ccc1 (Milestone 46 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Read docs/PORTFOLIO_TREND_ALERT_RULES.md.
8. Read docs/PORTFOLIO_ALERT_FOCUS_PREFERENCES.md.
9. Review the current codebase through commit 353ccc1.
10. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
11. Keep PRD.md and Architecture.md in the project root.
12. Use src/marketsentry/ as the Python package path.
13. Do not move PRD.md or Architecture.md into docs/.
14. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
15. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
16. Do not implement new Redfin live retrieval behavior in this milestone.
17. Do not run any live network calls in tests.
18. Do not make scheduled tasks run live retrieval by default.
19. Do not add walkability parsing or walkability fields.
20. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

## PM direction

Milestone 47 should add a **local email digest draft export** for portfolio focus alerts.

This milestone must **not send email**. It must not use SMTP, Gmail API, Outlook automation, webhooks, SMS, Twilio, Slack, Discord, or any outbound notification channel.

The goal is to generate a local, manually reviewable email-style draft from the existing focus alert digest:

- subject line suggestion
- plain-text body
- Markdown body
- optional `.eml` file if implemented using standard library only and with no sending
- local file export only
- clear “not sent” safety note
- manual copy/paste instructions
- dashboard visibility

This milestone must not add live retrieval, broaden scraping, change the Quiet Score gatekeeper, or automatically apply candidate/watchlist/alert actions.

This is a local read-only/reporting milestone. It must not change candidate decisions, watchlist status, alert status, Redfin source-of-truth fields, retrieval behavior, alert evaluation rules, or focus preferences. It must not infer seller intent. It must not make purchase recommendations.

## Critical project rules

1. Effective DOM v1 is listing-history-derived exposure without county reset integration.
2. Effective DOM v2 applies county-confirmed ownership transfer as a reset boundary when appropriate.
3. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
4. Churn Index remains reportable even when Effective DOM is reset.
5. Quiet Score is the gatekeeper and must remain unchanged.
6. Target is very high Quiet and very low Vibrancy.
7. Any mention of gas means natural gas supply/service evidence.
8. Walkability-type information is excluded.
9. Use neutral language. Do not infer seller intent.
10. Reports are analytical aids, not purchase recommendations.
11. Email digest drafts are local files only.
12. No outbound notifications should be sent in this milestone.

## Implement

### 1. Local email draft module

Create:

```text
src/marketsentry/portfolio_alert_email_digest.py
```

Required models:

- PortfolioAlertEmailDigestDraft
- PortfolioAlertEmailDigestSection
- PortfolioAlertEmailDigestExportResult
- PortfolioAlertEmailDigestSummary
- PortfolioAlertEmailDigestRunResult

Required functions:

- build_portfolio_alert_email_digest(...)
- build_email_digest_subject(...)
- build_email_digest_plain_text(...)
- build_email_digest_markdown(...)
- export_portfolio_alert_email_digest(...)
- summarize_portfolio_alert_email_digest(...)

Input sources:

- M46 focus digest/items from `portfolio_alert_focus.py`
- M45 alert history if needed
- M43/M44 alert rules only as context, not for mutation

Behavior:

- Read focus items using existing focus preference config if supplied.
- Generate a local email-like digest.
- Export files only.
- Do not send or queue any message.
- Do not connect to any service.
- Do not require any email address.
- Do not store credentials.
- Do not import smtplib or email-sending libraries except Python standard library `email` package if generating `.eml` file.
- `.eml` generation is optional and must remain local only.

## 2. Digest content

Include:

- subject suggestion
- generated timestamp
- safety note: local draft only, not sent
- alert focus profile used
- alert counts by severity
- top high-severity focus items
- persistent alerts
- aggregate burden alerts
- property-level degraded trend alerts
- recommended local review actions
- source files/reports used if available
- manual copy/paste instructions

Use neutral wording.

No purchase recommendations.

## 3. Export files

Export to:

```text
data/exports/portfolio_alert_email_digest_YYYYMMDD_HHMMSS.txt
data/exports/portfolio_alert_email_digest_YYYYMMDD_HHMMSS.md
```

Optional:

```text
data/exports/portfolio_alert_email_digest_YYYYMMDD_HHMMSS.eml
```

Only implement `.eml` if straightforward with Python standard library and no sending.

Required output metadata:

- output_paths
- subject
- focus_item_count
- high_count
- warning_count
- info_count
- generated_at
- sent_status = "not_sent"

## 4. CLI commands

Add:

```text
marketsentry portfolio-alert-email-digest
marketsentry export-portfolio-alert-email-digest
```

### portfolio-alert-email-digest

Options:

- --preference-config optional
- --limit optional default 25
- --db optional
- --exports-dir optional

Output:

- subject suggestion
- focus item count
- severity counts
- preview of first few lines
- explicit note: no email sent

### export-portfolio-alert-email-digest

Options:

- --preference-config optional
- --output-dir optional
- --format txt/md/both/all optional default both
- --include-eml optional default false
- --db optional
- --exports-dir optional

Output:

- report path(s)
- subject
- focus item count
- sent_status = not_sent
- explicit note: no email sent

## 5. Dashboard integration

Add **Portfolio Alert Email Draft** subsection.

Show:

- subject suggestion
- focus profile
- item counts
- latest email draft export path
- preview body
- safety note: local draft only; no outbound message sent

Dashboard remains read-only.

## 6. Scheduled script update

Update existing:

```text
scripts/run_portfolio_review_pack_report.bat
```

So it may optionally run:

- export-portfolio-alert-email-digest --format both

Script must still:

- not run live retrieval
- not use --force-live
- not run mutation/import commands
- not send outbound notifications
- not invoke SMTP/Gmail/Outlook/webhooks
- write logs to logs/scheduled/

Tests must verify scheduled script does not contain live retrieval, mutation, or outbound notification commands.

## 7. Tests

Add or update tests for:

- build digest with no focus items
- build digest with focus items
- subject line generation
- plain-text body generation
- Markdown body generation
- export txt
- export md
- optional eml export if implemented
- no email sent flag
- CLI portfolio-alert-email-digest
- CLI export-portfolio-alert-email-digest
- dashboard email draft data loads
- scheduled script safety
- no outbound notification imports or commands
- no candidate/watchlist/alert mutation
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-46 tests still pass

## 8. Documentation

Update README.md and docs/RUNBOOK.md with a "Local Email Digest Draft Export" section.

Update docs/WINDOWS_TASK_SCHEDULER.md with updated portfolio review pack scheduled script behavior if changed.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with a short section on creating a local email draft for manual review.

Update docs/PORTFOLIO_ALERT_FOCUS_PREFERENCES.md with a note that focused items can be rendered into a local email draft file.

Create:

```text
docs/PORTFOLIO_ALERT_EMAIL_DIGEST.md
```

Include:

- what the local email digest is
- what it is not
- file formats
- CLI examples
- manual copy/paste workflow
- no outbound notifications
- no credentials
- no SMTP/Gmail/Outlook integration

Create decision note:

```text
docs/decisions/046-local-email-digest-draft.md
```

Explain:

- why local draft follows focus preferences
- why no outbound notification is sent
- why no credentials are stored
- why scheduled script is local/report-only
- why candidate/watchlist/alert state is not automatically changed
- why Quiet Score gatekeeper is unchanged
- why walkability remains excluded

## Code standards

- Python 3.11+
- PEP8 compliant
- type hints required
- docstrings required for all functions
- remove unused imports
- use standard library only
- no browser automation
- no Playwright/Selenium
- no bypassing CAPTCHAs, paywalls, login walls, anti-bot protections, or technical access controls
- no network calls in tests
- do not import smtplib
- do not import requests/httpx/urllib.request for this feature
- preserve source file paths and timestamps for auditability
- use neutral language
- do not make purchase recommendations
- do not add walkability parsing or fields

## Quality gates

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- Existing portfolio alert focus digest works.
- Email digest draft exports text/Markdown.
- Optional `.eml` export, if implemented, is local-only.
- Dashboard email draft section loads.
- Scheduled portfolio review script remains safe.
- No candidate/watchlist/alert status mutations occur.
- No Redfin source-of-truth fields are overwritten.
- Quiet gatekeeper remains unchanged.
- No real network calls are performed in tests.
- No scheduled task invokes live retrieval, mutation commands, or outbound notifications.
- No SMTP/Gmail/Outlook/webhook/SMS code is added.
- Changes committed and pushed to origin/main.

## Completion report required

When finished, provide:

1. Summary of what you implemented.
2. Files created or modified.
3. Exact commands run.
4. Final test results with full pytest summary showing 100% pass.
5. Any dependency changes.
6. Any assumptions made.
7. Any blockers or risks remaining.
8. Example portfolio-alert-email-digest output.
9. Example email draft export paths and row/item counts.
10. Example subject line and first few body lines.
11. Dashboard Portfolio Alert Email Draft section added.
12. Scheduled script update added or explicitly not added.
13. Confirmation that email digest draft is local-only and does not send email.
14. Confirmation that no credentials are stored or requested.
15. Confirmation that email digest does not mutate candidate/watchlist/alert state.
16. Confirmation that email digest does not overwrite Redfin source-of-truth fields.
17. Confirmation that Quiet Score gatekeeper remains unchanged.
18. Confirmation that walkability fields were not added.
19. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
20. Confirmation that tests perform no real network calls.
21. Recommended next implementation step.
22. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 47 complete until all tests pass.
