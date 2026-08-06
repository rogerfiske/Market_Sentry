# Portfolio Alert Email Digest

## What It Is

The portfolio alert email digest is a local file export that generates an email-style draft from portfolio focus alert items. It produces a subject line suggestion, plain-text body, and Markdown body that can be manually copied into an email client for sharing.

## What It Is Not

- It does **not** send email
- It does **not** connect to SMTP, Gmail, Outlook, or any email service
- It does **not** use webhooks, SMS, Slack, Discord, or any outbound notification channel
- It does **not** store or request email credentials
- It does **not** queue messages for later delivery
- It does **not** mutate candidate, watchlist, or alert state
- It does **not** change alert evaluation rules or focus preferences
- It does **not** overwrite Redfin source-of-truth fields
- It does **not** modify the Quiet Score gatekeeper

## File Formats

The export produces these local files:

| Format | File Pattern | Description |
|--------|-------------|-------------|
| Plain text | `portfolio_alert_email_digest_YYYYMMDD_HHMMSS.txt` | Plain-text email body with subject line |
| Markdown | `portfolio_alert_email_digest_YYYYMMDD_HHMMSS.md` | Markdown-formatted email body |
| EML (optional) | `portfolio_alert_email_digest_YYYYMMDD_HHMMSS.eml` | RFC 2822 email file (local only, not sent) |

All files are written to `data/exports/` by default.

## CLI Examples

### Preview Digest

```bash
# Preview email digest draft with default settings
marketsentry portfolio-alert-email-digest

# Preview with custom focus preferences
marketsentry portfolio-alert-email-digest --preference-config config/portfolio_alert_highlight_preferences.json

# Limit to top 10 items
marketsentry portfolio-alert-email-digest --limit 10

# Use a specific database
marketsentry portfolio-alert-email-digest --db db/marketsentry.db
```

### Export Draft Files

```bash
# Export plain-text and Markdown drafts (default)
marketsentry export-portfolio-alert-email-digest --format both

# Export plain-text only
marketsentry export-portfolio-alert-email-digest --format txt

# Export Markdown only
marketsentry export-portfolio-alert-email-digest --format md

# Export all formats including .eml
marketsentry export-portfolio-alert-email-digest --format both --include-eml

# Export with custom output directory
marketsentry export-portfolio-alert-email-digest --output-dir reports/email_drafts

# Export with custom focus preferences
marketsentry export-portfolio-alert-email-digest --preference-config config/portfolio_alert_highlight_preferences.json --format both
```

## Manual Copy/Paste Workflow

1. Run `marketsentry export-portfolio-alert-email-digest --format both` to generate draft files
2. Open the exported `.txt` or `.md` file in a text editor
3. Copy the subject line from the file header
4. Paste it into the subject field of your email client
5. Copy the body text from the file
6. Paste it into the body of your email
7. Review and edit as needed before sending manually

If you generated the optional `.eml` file, you can open it directly in most email clients as a draft message. The `.eml` file is pre-formatted with subject and body but contains no recipient or sender information.

## Draft Content

Each email digest draft includes:

- **Subject line suggestion**: Generated from alert counts and date
- **Generated timestamp**: When the draft was created
- **Safety note**: Clearly states this is a local draft only, not sent
- **Alert focus profile**: Which preference profile was used
- **Alert counts by severity**: High, warning, and info counts
- **High-severity focus items**: Details of the most critical alerts
- **Persistent alerts**: Alerts that have persisted across multiple runs
- **Aggregate burden alerts**: Portfolio-wide burden indicators
- **Property-level degraded trend alerts**: Properties showing negative trends
- **Recommended local review actions**: Suggested next steps for the operator
- **Manual copy/paste instructions**: How to share the draft via email

## No Outbound Notifications

This module uses Python's standard library `email.message.EmailMessage` class solely for generating the optional `.eml` file format. It does **not** import `smtplib` or any email-sending library. The `email` package is used only for RFC 2822 message formatting.

No outbound notifications of any kind are sent by this module:

- No SMTP connections
- No Gmail API calls
- No Outlook automation
- No webhook calls
- No SMS/Twilio
- No Slack/Discord messages

## No Credentials

This module does not:

- Request email addresses
- Store passwords or API keys
- Use `getpass`, `keyring`, or credential managers
- Read environment variables for authentication
- Connect to any external authentication service

## Scheduled Script

The `scripts/run_portfolio_review_pack_report.bat` script includes `export-portfolio-alert-email-digest --format both` as part of the portfolio review pack report pipeline. This runs as a local file export only and does not send email or perform live retrieval.

## Dashboard

The Streamlit dashboard includes a **Portfolio Alert Email Draft** subsection showing:

- Subject line suggestion
- Focus profile name
- Sent status (always "not_sent")
- Focus item count and severity counts
- Body preview (expandable)
- Latest email draft export path
- Safety note: local draft only, no outbound message sent
