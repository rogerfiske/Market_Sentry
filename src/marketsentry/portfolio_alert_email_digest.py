"""Local Email Digest Draft Export for Portfolio Focus Alerts.

Generates a local, manually reviewable email-style draft from
existing focus alert digest items. Exports plain-text, Markdown,
and optional .eml files for manual copy/paste workflows.

This module is local-file-only. It does NOT send email. It does
NOT connect to any service. It does NOT use SMTP, Gmail, Outlook,
webhooks, SMS, or any outbound notification channel. It does NOT
require any email address or credentials.

No outbound notifications are sent.
No database writes are performed.
No candidate/watchlist/alert state is mutated.
"""

import logging
import os
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field

logger = logging.getLogger("marketsentry")

SAFETY_NOTE = (
    "LOCAL DRAFT ONLY - This email digest was generated locally "
    "and has NOT been sent. No outbound message was transmitted. "
    "To share this information, manually copy and paste the "
    "content into your preferred email client."
)

COPY_PASTE_INSTRUCTIONS = (
    "Manual copy/paste instructions:\n"
    "1. Open your preferred email client.\n"
    "2. Create a new message.\n"
    "3. Copy the subject line above into the Subject field.\n"
    "4. Copy the body content below into the message body.\n"
    "5. Add recipient addresses manually.\n"
    "6. Review the content before sending.\n"
    "7. Send from your email client when ready."
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PortfolioAlertEmailDigestSection(BaseModel):
    """A section within the email digest body."""

    heading: str = ""
    content: str = ""
    item_count: int = 0


class PortfolioAlertEmailDigestDraft(BaseModel):
    """A local email-style digest draft."""

    subject: str = ""
    plain_text_body: str = ""
    markdown_body: str = ""
    sections: List[PortfolioAlertEmailDigestSection] = Field(
        default_factory=list
    )
    focus_profile: str = ""
    focus_item_count: int = 0
    high_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    generated_at: str = ""
    sent_status: str = "not_sent"
    safety_note: str = SAFETY_NOTE


class PortfolioAlertEmailDigestSummary(BaseModel):
    """Summary of an email digest draft."""

    subject: str = ""
    focus_profile: str = ""
    focus_item_count: int = 0
    high_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    section_count: int = 0
    generated_at: str = ""
    sent_status: str = "not_sent"


class PortfolioAlertEmailDigestExportResult(BaseModel):
    """Result of exporting an email digest draft."""

    output_paths: List[str] = Field(default_factory=list)
    subject: str = ""
    focus_item_count: int = 0
    high_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    generated_at: str = ""
    sent_status: str = "not_sent"


class PortfolioAlertEmailDigestRunResult(BaseModel):
    """Result container for email digest operations."""

    draft: Optional[PortfolioAlertEmailDigestDraft] = None
    export_result: Optional[
        PortfolioAlertEmailDigestExportResult
    ] = None
    summary: Optional[PortfolioAlertEmailDigestSummary] = None
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def build_portfolio_alert_email_digest(
    preference_config: Optional[Union[str, Path]] = None,
    db_path: Optional[str] = None,
    exports_dir: str = "data/exports",
    limit: int = 25,
) -> PortfolioAlertEmailDigestDraft:
    """Build a local email digest draft from focus alert items.

    Reads focus items using existing M46 preference config and
    generates an email-style draft with subject, plain-text body,
    and Markdown body.

    This function does NOT send email. It does NOT connect to
    any service. No outbound notifications.

    Args:
        preference_config: Optional path to highlight prefs JSON.
        db_path: Optional path to SQLite database.
        exports_dir: Directory with export files.
        limit: Maximum focus items to include.

    Returns:
        PortfolioAlertEmailDigestDraft with generated content.
    """
    from marketsentry.portfolio_alert_focus import (
        build_portfolio_alert_focus_items,
        load_portfolio_alert_highlight_preferences,
        summarize_portfolio_alert_focus,
    )

    prefs = load_portfolio_alert_highlight_preferences(
        preference_config
    )
    if not prefs.is_valid:
        prefs = load_portfolio_alert_highlight_preferences(None)

    if limit > 0:
        prefs.max_items = limit

    items = build_portfolio_alert_focus_items(
        prefs=prefs,
        db_path=db_path,
        exports_dir=exports_dir,
    )
    summary = summarize_portfolio_alert_focus(items, prefs)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    subject = build_email_digest_subject(
        high_count=summary.high_count,
        warning_count=summary.warning_count,
        total_items=summary.total_focus_items,
        profile_name=prefs.profile_name,
    )

    sections = _build_sections(items, summary, prefs)

    plain_text = build_email_digest_plain_text(
        subject=subject,
        sections=sections,
        summary=summary,
        prefs_profile=prefs.profile_name,
        generated_at=now,
    )

    markdown = build_email_digest_markdown(
        subject=subject,
        sections=sections,
        summary=summary,
        prefs_profile=prefs.profile_name,
        generated_at=now,
    )

    draft = PortfolioAlertEmailDigestDraft(
        subject=subject,
        plain_text_body=plain_text,
        markdown_body=markdown,
        sections=sections,
        focus_profile=prefs.profile_name,
        focus_item_count=summary.total_focus_items,
        high_count=summary.high_count,
        warning_count=summary.warning_count,
        info_count=summary.info_count,
        generated_at=now,
        sent_status="not_sent",
    )

    return draft


def build_email_digest_subject(
    high_count: int = 0,
    warning_count: int = 0,
    total_items: int = 0,
    profile_name: str = "",
) -> str:
    """Build a suggested subject line for the email digest.

    Args:
        high_count: Number of high-severity focus items.
        warning_count: Number of warning-severity focus items.
        total_items: Total number of focus items.
        profile_name: Focus profile name.

    Returns:
        Subject line string.
    """
    date_str = datetime.now().strftime("%Y-%m-%d")

    if total_items == 0:
        return (
            f"[Market Sentry] Portfolio Alert Focus Digest "
            f"- {date_str} - No items"
        )

    parts = []
    if high_count > 0:
        parts.append(f"{high_count} high")
    if warning_count > 0:
        parts.append(f"{warning_count} warning")

    severity_summary = ", ".join(parts) if parts else "info only"

    return (
        f"[Market Sentry] Portfolio Alert Focus Digest "
        f"- {date_str} - {total_items} items "
        f"({severity_summary})"
    )


def build_email_digest_plain_text(
    subject: str,
    sections: List[PortfolioAlertEmailDigestSection],
    summary: "PortfolioAlertEmailDigestSummary" = None,
    prefs_profile: str = "",
    generated_at: str = "",
) -> str:
    """Build the plain-text body of the email digest.

    Args:
        subject: Subject line.
        sections: Digest sections.
        summary: Optional summary object.
        prefs_profile: Focus profile name.
        generated_at: Generation timestamp.

    Returns:
        Plain-text body string.
    """
    lines: List[str] = []

    lines.append(SAFETY_NOTE)
    lines.append("")
    lines.append("=" * 60)
    lines.append(f"Subject: {subject}")
    lines.append("=" * 60)
    lines.append("")
    lines.append(
        f"Generated: {generated_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    lines.append(f"Focus profile: {prefs_profile}")
    lines.append(f"Status: NOT SENT (local draft only)")
    lines.append("")

    for section in sections:
        lines.append("-" * 40)
        lines.append(section.heading.upper())
        lines.append("-" * 40)
        lines.append(section.content)
        lines.append("")

    lines.append("-" * 40)
    lines.append("MANUAL COPY/PASTE INSTRUCTIONS")
    lines.append("-" * 40)
    lines.append(COPY_PASTE_INSTRUCTIONS)
    lines.append("")

    lines.append(
        "This report is a local analytical review aid. "
        "It does not make purchase recommendations, infer "
        "seller intent, or mutate candidate/watchlist/alert "
        "state. No outbound notifications were sent."
    )

    return "\n".join(lines)


def build_email_digest_markdown(
    subject: str,
    sections: List[PortfolioAlertEmailDigestSection],
    summary: "PortfolioAlertEmailDigestSummary" = None,
    prefs_profile: str = "",
    generated_at: str = "",
) -> str:
    """Build the Markdown body of the email digest.

    Args:
        subject: Subject line.
        sections: Digest sections.
        summary: Optional summary object.
        prefs_profile: Focus profile name.
        generated_at: Generation timestamp.

    Returns:
        Markdown body string.
    """
    lines: List[str] = []

    lines.append("# Portfolio Alert Email Digest Draft")
    lines.append("")
    lines.append(f"> {SAFETY_NOTE}")
    lines.append("")
    lines.append(f"**Subject:** {subject}")
    lines.append("")
    lines.append(
        f"**Generated:** "
        f"{generated_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    lines.append(f"**Focus profile:** {prefs_profile}")
    lines.append(f"**Status:** NOT SENT (local draft only)")
    lines.append("")

    for section in sections:
        lines.append(f"## {section.heading}")
        lines.append("")
        lines.append(section.content)
        lines.append("")

    lines.append("## Manual Copy/Paste Instructions")
    lines.append("")
    lines.append(COPY_PASTE_INSTRUCTIONS)
    lines.append("")
    lines.append(
        "*This report is a local analytical review aid. "
        "It does not make purchase recommendations, infer "
        "seller intent, or mutate candidate/watchlist/alert "
        "state. No outbound notifications were sent.*"
    )

    return "\n".join(lines)


def export_portfolio_alert_email_digest(
    preference_config: Optional[Union[str, Path]] = None,
    db_path: Optional[str] = None,
    exports_dir: str = "data/exports",
    output_dir: Optional[str] = None,
    fmt: str = "both",
    include_eml: bool = False,
    limit: int = 25,
) -> PortfolioAlertEmailDigestExportResult:
    """Export a local email digest draft to files.

    Exports plain-text and/or Markdown files. Optionally
    exports a .eml file using Python standard library only.

    Does NOT send email. Does NOT connect to any service.
    No outbound notifications. No credentials required.

    Args:
        preference_config: Optional path to highlight prefs JSON.
        db_path: Optional path to SQLite database.
        exports_dir: Directory with export files.
        output_dir: Output directory. Defaults to exports_dir.
        fmt: Export format: txt, md, both, or all.
        include_eml: Whether to include .eml export.
        limit: Maximum focus items to include.

    Returns:
        PortfolioAlertEmailDigestExportResult.
    """
    if output_dir is None:
        output_dir = exports_dir

    draft = build_portfolio_alert_email_digest(
        preference_config=preference_config,
        db_path=db_path,
        exports_dir=exports_dir,
        limit=limit,
    )

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: List[str] = []

    if fmt in ("txt", "both", "all"):
        txt_path = os.path.join(
            output_dir,
            f"portfolio_alert_email_digest_{ts}.txt",
        )
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(draft.plain_text_body)
        paths.append(txt_path)

    if fmt in ("md", "both", "all"):
        md_path = os.path.join(
            output_dir,
            f"portfolio_alert_email_digest_{ts}.md",
        )
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(draft.markdown_body)
        paths.append(md_path)

    if include_eml or fmt == "all":
        eml_path = os.path.join(
            output_dir,
            f"portfolio_alert_email_digest_{ts}.eml",
        )
        _write_eml_draft(eml_path, draft)
        paths.append(eml_path)

    result = PortfolioAlertEmailDigestExportResult(
        output_paths=paths,
        subject=draft.subject,
        focus_item_count=draft.focus_item_count,
        high_count=draft.high_count,
        warning_count=draft.warning_count,
        info_count=draft.info_count,
        generated_at=draft.generated_at,
        sent_status="not_sent",
    )

    return result


def summarize_portfolio_alert_email_digest(
    draft: PortfolioAlertEmailDigestDraft,
) -> PortfolioAlertEmailDigestSummary:
    """Summarize an email digest draft.

    Args:
        draft: The email digest draft.

    Returns:
        PortfolioAlertEmailDigestSummary.
    """
    return PortfolioAlertEmailDigestSummary(
        subject=draft.subject,
        focus_profile=draft.focus_profile,
        focus_item_count=draft.focus_item_count,
        high_count=draft.high_count,
        warning_count=draft.warning_count,
        info_count=draft.info_count,
        section_count=len(draft.sections),
        generated_at=draft.generated_at,
        sent_status="not_sent",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_sections(
    items: list,
    summary: object,
    prefs: object,
) -> List[PortfolioAlertEmailDigestSection]:
    """Build digest sections from focus items.

    Args:
        items: Focus items from M46.
        summary: Focus summary from M46.
        prefs: Highlight preferences.

    Returns:
        List of PortfolioAlertEmailDigestSection.
    """
    sections: List[PortfolioAlertEmailDigestSection] = []

    # Summary section
    high_count = getattr(summary, "high_count", 0)
    warning_count = getattr(summary, "warning_count", 0)
    info_count = getattr(summary, "info_count", 0)
    total = getattr(summary, "total_focus_items", 0)

    summary_content = (
        f"Total focus items: {total}\n"
        f"High severity: {high_count}\n"
        f"Warning severity: {warning_count}\n"
        f"Info severity: {info_count}"
    )
    sections.append(PortfolioAlertEmailDigestSection(
        heading="Alert Counts",
        content=summary_content,
        item_count=total,
    ))

    # High severity items
    high_items = [
        i for i in items if getattr(i, "severity", "") == "high"
    ]
    if high_items:
        lines = []
        for item in high_items:
            addr = getattr(item, "address", "")
            addr = addr[:35] if addr else "N/A"
            atype = getattr(item, "alert_type", "")
            reason = getattr(item, "focus_reason", "")
            persist = getattr(item, "persistence_count", 0)
            lines.append(
                f"- [{addr}] {atype}"
                f" (persistence: {persist})"
                f" - {reason}"
            )
        sections.append(PortfolioAlertEmailDigestSection(
            heading="High Severity Focus Items",
            content="\n".join(lines),
            item_count=len(high_items),
        ))

    # Persistent alerts (seen in 2+ runs)
    persistent_items = [
        i for i in items
        if getattr(i, "persistence_count", 0) >= 2
    ]
    if persistent_items:
        lines = []
        for item in persistent_items:
            addr = getattr(item, "address", "")
            addr = addr[:35] if addr else "N/A"
            atype = getattr(item, "alert_type", "")
            sev = getattr(item, "severity", "")
            persist = getattr(item, "persistence_count", 0)
            lines.append(
                f"- [{addr}] {atype}"
                f" ({sev}, seen {persist} times)"
            )
        sections.append(PortfolioAlertEmailDigestSection(
            heading="Persistent Alerts",
            content="\n".join(lines),
            item_count=len(persistent_items),
        ))

    # Aggregate burden alerts
    burden_items = [
        i for i in items
        if "burden" in getattr(
            i, "alert_type", ""
        ).lower()
    ]
    if burden_items:
        lines = []
        for item in burden_items:
            atype = getattr(item, "alert_type", "")
            sev = getattr(item, "severity", "")
            msg = getattr(item, "message", "")
            lines.append(
                f"- {atype} ({sev})"
                f"{': ' + msg[:50] if msg else ''}"
            )
        sections.append(PortfolioAlertEmailDigestSection(
            heading="Aggregate Burden Alerts",
            content="\n".join(lines),
            item_count=len(burden_items),
        ))

    # Property-level degraded trend alerts
    degraded_items = [
        i for i in items
        if "degraded" in getattr(
            i, "alert_type", ""
        ).lower()
        or "property" in getattr(
            i, "focus_reason", ""
        ).lower()
    ]
    if degraded_items:
        lines = []
        for item in degraded_items:
            addr = getattr(item, "address", "")
            addr = addr[:35] if addr else "N/A"
            atype = getattr(item, "alert_type", "")
            sev = getattr(item, "severity", "")
            lines.append(
                f"- [{addr}] {atype} ({sev})"
            )
        sections.append(PortfolioAlertEmailDigestSection(
            heading="Property-Level Trend Alerts",
            content="\n".join(lines),
            item_count=len(degraded_items),
        ))

    # Recommended local review actions
    action_items = [
        i for i in items
        if getattr(i, "recommended_local_action", "")
    ]
    if action_items:
        lines = []
        seen_actions = set()
        for item in action_items:
            action = getattr(
                item, "recommended_local_action", ""
            )
            if action and action not in seen_actions:
                lines.append(f"- {action}")
                seen_actions.add(action)
        if lines:
            sections.append(PortfolioAlertEmailDigestSection(
                heading="Recommended Local Review Actions",
                content="\n".join(lines),
                item_count=len(lines),
            ))

    # If no items, add a note
    if not items:
        sections.append(PortfolioAlertEmailDigestSection(
            heading="Status",
            content=(
                "No focus items matched the current "
                "preferences. No alerts require attention "
                "at this time based on the active profile."
            ),
            item_count=0,
        ))

    return sections


def _write_eml_draft(
    path: str,
    draft: PortfolioAlertEmailDigestDraft,
) -> None:
    """Write a local .eml draft file using Python standard library.

    This creates a local RFC 2822 email file that can be opened
    in email clients for review. It does NOT send the message.
    No SMTP connection is made.

    Args:
        path: Output file path.
        draft: Email digest draft.
    """
    msg = EmailMessage()
    msg["Subject"] = draft.subject
    msg["From"] = "Market Sentry Local Draft <noreply@local>"
    msg["To"] = "(not sent - add recipients manually)"
    msg["Date"] = draft.generated_at
    msg["X-Market-Sentry-Status"] = "NOT_SENT"
    msg["X-Market-Sentry-Note"] = (
        "Local draft only. Not transmitted."
    )

    msg.set_content(draft.plain_text_body)

    with open(path, "w", encoding="utf-8") as f:
        f.write(msg.as_string())
