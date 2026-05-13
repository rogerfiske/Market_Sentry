"""Tests for Milestone 47 - Local Email Digest Draft Export.

Tests email digest draft building, subject generation, plain-text
and Markdown body generation, file exports, optional .eml export,
CLI commands, dashboard imports, scheduled script safety, and
guard-rail constraints.

No real network calls. No email is sent. No database mutations.
No outbound notifications.
"""

import csv
import json
import os
import tempfile
from pathlib import Path

import pytest

from marketsentry.portfolio_alert_email_digest import (
    COPY_PASTE_INSTRUCTIONS,
    SAFETY_NOTE,
    PortfolioAlertEmailDigestDraft,
    PortfolioAlertEmailDigestExportResult,
    PortfolioAlertEmailDigestRunResult,
    PortfolioAlertEmailDigestSection,
    PortfolioAlertEmailDigestSummary,
    build_email_digest_markdown,
    build_email_digest_plain_text,
    build_email_digest_subject,
    build_portfolio_alert_email_digest,
    export_portfolio_alert_email_digest,
    summarize_portfolio_alert_email_digest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_digest_csv(exports_dir: str) -> None:
    """Create a fake M43 trend alert digest CSV for testing."""
    csv_path = os.path.join(
        exports_dir,
        "portfolio_trend_alert_digest_20260101_000000.csv",
    )
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "alert_id", "alert_scope",
                "property_id", "candidate_id",
                "address", "severity", "alert_type",
                "message", "metric_name",
                "previous_value", "current_value",
                "delta_value",
                "recommended_local_action",
                "source_pack_file", "generated_at",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "alert_id": "burden_high_80",
            "alert_scope": "portfolio",
            "property_id": "",
            "candidate_id": "",
            "address": "",
            "severity": "high",
            "alert_type": "aggregate_burden_high",
            "message": "Aggregate review burden is 85",
            "metric_name": "aggregate_review_burden_score",
            "previous_value": "70",
            "current_value": "85",
            "delta_value": "15",
            "recommended_local_action": (
                "Review top burden contributors"
            ),
            "source_pack_file": "test.csv",
            "generated_at": "2026-01-01",
        })
        writer.writerow({
            "alert_id": "property_degraded",
            "alert_scope": "property",
            "property_id": "100",
            "candidate_id": "50",
            "address": "123 Test St",
            "severity": "warning",
            "alert_type": "property_degraded",
            "message": "Trend direction degraded",
            "metric_name": "trend_direction",
            "previous_value": "stable",
            "current_value": "degraded",
            "delta_value": "",
            "recommended_local_action": (
                "Review property trend"
            ),
            "source_pack_file": "test.csv",
            "generated_at": "2026-01-01",
        })
        writer.writerow({
            "alert_id": "churn_increase",
            "alert_scope": "property",
            "property_id": "101",
            "candidate_id": "51",
            "address": "456 Oak Ave",
            "severity": "warning",
            "alert_type": "churn_increase",
            "message": "Churn Index increased",
            "metric_name": "churn_index_delta",
            "previous_value": "1.0",
            "current_value": "2.5",
            "delta_value": "1.5",
            "recommended_local_action": (
                "Review churn history"
            ),
            "source_pack_file": "test.csv",
            "generated_at": "2026-01-01",
        })


# ---------------------------------------------------------------------------
# Build digest tests
# ---------------------------------------------------------------------------

class TestBuildDigest:
    """Email digest draft building."""

    def test_build_with_no_focus_items(self):
        """Build digest with no available focus items."""
        with tempfile.TemporaryDirectory() as tmp:
            draft = build_portfolio_alert_email_digest(
                exports_dir=tmp,
            )
            assert isinstance(
                draft, PortfolioAlertEmailDigestDraft
            )
            assert draft.sent_status == "not_sent"
            assert draft.focus_item_count == 0
            assert draft.subject != ""
            assert "No items" in draft.subject

    def test_build_with_focus_items(self):
        """Build digest with focus items from CSV."""
        with tempfile.TemporaryDirectory() as tmp:
            _create_test_digest_csv(tmp)
            draft = build_portfolio_alert_email_digest(
                exports_dir=tmp,
            )
            assert draft.focus_item_count >= 1
            assert draft.sent_status == "not_sent"
            assert draft.plain_text_body != ""
            assert draft.markdown_body != ""
            assert len(draft.sections) >= 1

    def test_build_preserves_safety_note(self):
        """Draft always includes safety note."""
        with tempfile.TemporaryDirectory() as tmp:
            draft = build_portfolio_alert_email_digest(
                exports_dir=tmp,
            )
            assert "NOT" in draft.safety_note
            assert "not sent" in draft.safety_note.lower() or (
                "NOT been sent" in draft.safety_note
            )


# ---------------------------------------------------------------------------
# Subject line tests
# ---------------------------------------------------------------------------

class TestSubjectLine:
    """Subject line generation."""

    def test_subject_with_no_items(self):
        """Subject line for empty digest."""
        subject = build_email_digest_subject(
            total_items=0,
        )
        assert "Market Sentry" in subject
        assert "No items" in subject

    def test_subject_with_high_items(self):
        """Subject line includes high count."""
        subject = build_email_digest_subject(
            high_count=3,
            warning_count=2,
            total_items=5,
        )
        assert "3 high" in subject
        assert "2 warning" in subject
        assert "5 items" in subject

    def test_subject_with_warnings_only(self):
        """Subject line with warnings only."""
        subject = build_email_digest_subject(
            high_count=0,
            warning_count=4,
            total_items=4,
        )
        assert "4 warning" in subject
        assert "high" not in subject.lower() or (
            "0 high" not in subject
        )

    def test_subject_includes_date(self):
        """Subject line includes date."""
        from datetime import datetime
        subject = build_email_digest_subject(
            total_items=1,
        )
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in subject


# ---------------------------------------------------------------------------
# Plain-text body tests
# ---------------------------------------------------------------------------

class TestPlainTextBody:
    """Plain-text body generation."""

    def test_plain_text_has_safety_note(self):
        """Plain-text body includes safety note."""
        body = build_email_digest_plain_text(
            subject="Test Subject",
            sections=[],
            prefs_profile="test",
            generated_at="2026-01-01 00:00:00",
        )
        assert "LOCAL DRAFT ONLY" in body
        assert "NOT been sent" in body

    def test_plain_text_has_subject(self):
        """Plain-text body includes subject."""
        body = build_email_digest_plain_text(
            subject="My Test Subject",
            sections=[],
            prefs_profile="test",
        )
        assert "My Test Subject" in body

    def test_plain_text_has_copy_paste(self):
        """Plain-text body includes copy/paste instructions."""
        body = build_email_digest_plain_text(
            subject="Test",
            sections=[],
        )
        assert "copy" in body.lower()
        assert "paste" in body.lower()

    def test_plain_text_has_sections(self):
        """Plain-text body renders sections."""
        sections = [
            PortfolioAlertEmailDigestSection(
                heading="Test Section",
                content="Test content here",
                item_count=1,
            ),
        ]
        body = build_email_digest_plain_text(
            subject="Test",
            sections=sections,
        )
        assert "TEST SECTION" in body
        assert "Test content here" in body


# ---------------------------------------------------------------------------
# Markdown body tests
# ---------------------------------------------------------------------------

class TestMarkdownBody:
    """Markdown body generation."""

    def test_markdown_has_title(self):
        """Markdown body has title heading."""
        body = build_email_digest_markdown(
            subject="Test Subject",
            sections=[],
        )
        assert "# Portfolio Alert Email Digest Draft" in body

    def test_markdown_has_safety_note(self):
        """Markdown body includes safety note."""
        body = build_email_digest_markdown(
            subject="Test",
            sections=[],
        )
        assert "LOCAL DRAFT ONLY" in body

    def test_markdown_has_subject(self):
        """Markdown body includes subject."""
        body = build_email_digest_markdown(
            subject="My Subject Line",
            sections=[],
        )
        assert "My Subject Line" in body

    def test_markdown_has_sections(self):
        """Markdown body renders sections."""
        sections = [
            PortfolioAlertEmailDigestSection(
                heading="High Severity Focus Items",
                content="- Item 1\n- Item 2",
                item_count=2,
            ),
        ]
        body = build_email_digest_markdown(
            subject="Test",
            sections=sections,
        )
        assert "## High Severity Focus Items" in body
        assert "Item 1" in body


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------

class TestExport:
    """Email digest export tests."""

    def test_export_txt(self):
        """Export plain-text file."""
        with tempfile.TemporaryDirectory() as tmp:
            result = export_portfolio_alert_email_digest(
                exports_dir=tmp,
                output_dir=tmp,
                fmt="txt",
            )
            assert isinstance(
                result, PortfolioAlertEmailDigestExportResult
            )
            txt_paths = [
                p for p in result.output_paths
                if p.endswith(".txt")
            ]
            assert len(txt_paths) == 1
            content = Path(txt_paths[0]).read_text(
                encoding="utf-8"
            )
            assert "LOCAL DRAFT ONLY" in content
            assert result.sent_status == "not_sent"

    def test_export_md(self):
        """Export Markdown file."""
        with tempfile.TemporaryDirectory() as tmp:
            result = export_portfolio_alert_email_digest(
                exports_dir=tmp,
                output_dir=tmp,
                fmt="md",
            )
            md_paths = [
                p for p in result.output_paths
                if p.endswith(".md")
            ]
            assert len(md_paths) == 1
            content = Path(md_paths[0]).read_text(
                encoding="utf-8"
            )
            assert "Portfolio Alert Email Digest" in content

    def test_export_both(self):
        """Export both txt and md files."""
        with tempfile.TemporaryDirectory() as tmp:
            result = export_portfolio_alert_email_digest(
                exports_dir=tmp,
                output_dir=tmp,
                fmt="both",
            )
            txt_count = sum(
                1 for p in result.output_paths
                if p.endswith(".txt")
            )
            md_count = sum(
                1 for p in result.output_paths
                if p.endswith(".md")
            )
            assert txt_count == 1
            assert md_count == 1

    def test_export_eml(self):
        """Export .eml file when requested."""
        with tempfile.TemporaryDirectory() as tmp:
            result = export_portfolio_alert_email_digest(
                exports_dir=tmp,
                output_dir=tmp,
                fmt="txt",
                include_eml=True,
            )
            eml_paths = [
                p for p in result.output_paths
                if p.endswith(".eml")
            ]
            assert len(eml_paths) == 1
            content = Path(eml_paths[0]).read_text(
                encoding="utf-8"
            )
            assert "Subject:" in content
            assert "NOT_SENT" in content

    def test_export_all_format(self):
        """Export all formats including eml."""
        with tempfile.TemporaryDirectory() as tmp:
            result = export_portfolio_alert_email_digest(
                exports_dir=tmp,
                output_dir=tmp,
                fmt="all",
            )
            exts = {
                Path(p).suffix for p in result.output_paths
            }
            assert ".txt" in exts
            assert ".md" in exts
            assert ".eml" in exts

    def test_no_email_sent_flag(self):
        """Export result always shows not_sent."""
        with tempfile.TemporaryDirectory() as tmp:
            result = export_portfolio_alert_email_digest(
                exports_dir=tmp,
                output_dir=tmp,
            )
            assert result.sent_status == "not_sent"


# ---------------------------------------------------------------------------
# Summary tests
# ---------------------------------------------------------------------------

class TestSummary:
    """Email digest summary tests."""

    def test_summary_from_draft(self):
        """Summary correctly reflects draft contents."""
        draft = PortfolioAlertEmailDigestDraft(
            subject="Test Subject",
            focus_profile="test_profile",
            focus_item_count=5,
            high_count=2,
            warning_count=3,
            info_count=0,
            sections=[
                PortfolioAlertEmailDigestSection(
                    heading="s1"
                ),
                PortfolioAlertEmailDigestSection(
                    heading="s2"
                ),
            ],
            generated_at="2026-01-01",
        )
        summary = summarize_portfolio_alert_email_digest(draft)
        assert summary.subject == "Test Subject"
        assert summary.focus_profile == "test_profile"
        assert summary.focus_item_count == 5
        assert summary.high_count == 2
        assert summary.warning_count == 3
        assert summary.section_count == 2
        assert summary.sent_status == "not_sent"


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:
    """CLI command tests."""

    def test_cli_portfolio_alert_email_digest(self):
        """portfolio-alert-email-digest CLI command runs."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            result = runner.invoke(
                app,
                [
                    "portfolio-alert-email-digest",
                    "--exports-dir", tmp,
                ],
            )
            assert result.exit_code == 0
            assert "Email Digest" in result.output
            assert "No email sent" in result.output

    def test_cli_export_portfolio_alert_email_digest(self):
        """export-portfolio-alert-email-digest CLI runs."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            result = runner.invoke(
                app,
                [
                    "export-portfolio-alert-email-digest",
                    "--exports-dir", tmp,
                    "--output-dir", tmp,
                    "--format", "both",
                ],
            )
            assert result.exit_code == 0
            assert "Email Digest" in result.output
            assert "No email sent" in result.output

    def test_cli_export_with_eml(self):
        """export-portfolio-alert-email-digest with --include-eml."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            result = runner.invoke(
                app,
                [
                    "export-portfolio-alert-email-digest",
                    "--exports-dir", tmp,
                    "--output-dir", tmp,
                    "--format", "txt",
                    "--include-eml",
                ],
            )
            assert result.exit_code == 0
            assert ".eml" in result.output


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------

class TestDashboard:
    """Dashboard email draft tests."""

    def test_dashboard_email_imports(self):
        """Dashboard email digest imports work."""
        from marketsentry.portfolio_alert_email_digest import (
            build_portfolio_alert_email_digest,
            summarize_portfolio_alert_email_digest,
        )
        draft = build_portfolio_alert_email_digest()
        summary = summarize_portfolio_alert_email_digest(draft)
        assert summary.sent_status == "not_sent"

    def test_dashboard_email_data_loads(self):
        """Dashboard email draft data loads with defaults."""
        draft = build_portfolio_alert_email_digest()
        assert draft.subject != ""
        assert draft.sent_status == "not_sent"
        assert draft.generated_at != ""


# ---------------------------------------------------------------------------
# Scheduled script safety tests
# ---------------------------------------------------------------------------

class TestScheduledScriptSafety:
    """Scheduled script safety checks."""

    def test_script_contains_email_digest_command(self):
        """Script contains the email digest command."""
        script = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        ).read_text(encoding="utf-8")
        assert (
            "export-portfolio-alert-email-digest" in script
        )

    def test_no_live_retrieval(self):
        """Script has no live retrieval commands."""
        script = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        ).read_text(encoding="utf-8")
        lower = script.lower()
        assert "--force-live" not in lower
        assert "retrieve-candidates" not in lower
        assert "scrape" not in lower

    def test_no_mutation_commands(self):
        """Script has no mutation commands."""
        script = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        ).read_text(encoding="utf-8")
        lower = script.lower()
        assert "import-candidates" not in lower
        assert "apply-triage" not in lower
        assert "update-decision" not in lower

    def test_no_outbound_notifications(self):
        """Script has no outbound notification commands."""
        script = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        ).read_text(encoding="utf-8")
        lower = script.lower()
        assert "send-email" not in lower
        assert "send-sms" not in lower

    def test_no_smtp_in_script(self):
        """Script has no SMTP/Gmail/Outlook commands."""
        script = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        ).read_text(encoding="utf-8")
        lower = script.lower()
        assert "smtp" not in lower
        assert "gmail" not in lower
        assert "outlook" not in lower


# ---------------------------------------------------------------------------
# Guard-rail constraint tests
# ---------------------------------------------------------------------------

class TestNoOutboundNotifications:
    """No outbound notification behavior."""

    def test_module_no_smtplib(self):
        """Module does not import smtplib."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "import smtplib" not in source

    def test_module_no_twilio(self):
        """Module does not import Twilio."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "import twilio" not in source

    def test_module_no_http_libs(self):
        """Module does not import HTTP libraries."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "import requests" not in source
        assert "import httpx" not in source

    def test_module_no_smtp_connect(self):
        """Module does not connect to SMTP."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "SMTP(" not in source
        assert "smtp.connect" not in source
        assert "smtp.login" not in source
        assert "smtp.send" not in source

    def test_module_no_gmail_outlook_integration(self):
        """Module does not integrate with Gmail or Outlook.

        Words may appear in safety documentation (saying we do
        NOT use them). Check for actual import/connection code.
        """
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "import gmail" not in source.lower()
        assert "from gmail" not in source.lower()
        assert "import outlook" not in source.lower()
        assert "GmailAPI" not in source
        assert "OutlookClient" not in source

    def test_module_no_credential_storage(self):
        """Module does not store or request credentials.

        Words may appear in safety documentation. Check for
        actual credential handling patterns.
        """
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "getpass" not in source
        assert "keyring" not in source
        assert "import credentials" not in source.lower()
        assert "os.environ[" not in source or (
            "PASSWORD" not in source
        )


class TestNoMutation:
    """No candidate/watchlist/alert state mutation."""

    def test_no_candidate_mutation(self):
        """Module does not mutate candidates."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "UPDATE candidate_review_queue" not in source
        assert "DELETE FROM candidate_review_queue" not in source

    def test_no_watchlist_mutation(self):
        """Module does not mutate watchlist."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "UPDATE watched_properties" not in source
        assert "DELETE FROM watched_properties" not in source

    def test_no_alert_status_mutation(self):
        """Module does not mutate alert status."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "UPDATE cross_site_trend_alerts" not in source

    def test_no_database_writes(self):
        """Module performs no database writes."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "INSERT INTO" not in source
        assert "DELETE FROM" not in source


class TestNoRedfinOverwrite:
    """No Redfin source-of-truth overwrite."""

    def test_no_redfin_field_writes(self):
        """Module does not write Redfin fields."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "UPDATE watched_properties SET" not in source
        assert (
            "UPDATE candidate_review_queue SET" not in source
        )


class TestQuietGatekeeper:
    """Quiet Score gatekeeper remains unchanged."""

    def test_no_quiet_score_modification(self):
        """Module does not modify Quiet Score."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "SET quiet_score" not in source
        assert "quiet_gatekeeper" not in source


class TestNoWalkability:
    """No walkability fields added."""

    def test_no_walkability_fields(self):
        """Module does not reference walkability fields."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "walk_score" not in source.lower()
        assert "transit_score" not in source.lower()
        assert "walkability" not in source.lower()


class TestNoBrowserAutomation:
    """No browser automation."""

    def test_no_playwright(self):
        """Module does not use Playwright."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "import playwright" not in source.lower()
        assert "from playwright" not in source.lower()

    def test_no_selenium(self):
        """Module does not use Selenium."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "import selenium" not in source.lower()
        assert "from selenium" not in source.lower()


class TestNoNetworkCalls:
    """No real network calls in tests or module."""

    def test_no_requests_import(self):
        """Module does not import network libraries."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "import requests" not in source
        assert "import httpx" not in source
        assert "import urllib.request" not in source

    def test_no_socket_usage(self):
        """Module does not use sockets."""
        source = Path(
            "src/marketsentry/"
            "portfolio_alert_email_digest.py"
        ).read_text(encoding="utf-8")
        assert "import socket" not in source


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestModels:
    """Model instantiation tests."""

    def test_draft_defaults(self):
        """PortfolioAlertEmailDigestDraft has defaults."""
        d = PortfolioAlertEmailDigestDraft()
        assert d.subject == ""
        assert d.sent_status == "not_sent"
        assert d.safety_note == SAFETY_NOTE

    def test_section_defaults(self):
        """PortfolioAlertEmailDigestSection has defaults."""
        s = PortfolioAlertEmailDigestSection()
        assert s.heading == ""
        assert s.item_count == 0

    def test_summary_defaults(self):
        """PortfolioAlertEmailDigestSummary has defaults."""
        s = PortfolioAlertEmailDigestSummary()
        assert s.sent_status == "not_sent"
        assert s.focus_item_count == 0

    def test_export_result_defaults(self):
        """PortfolioAlertEmailDigestExportResult has defaults."""
        r = PortfolioAlertEmailDigestExportResult()
        assert r.output_paths == []
        assert r.sent_status == "not_sent"

    def test_run_result_defaults(self):
        """PortfolioAlertEmailDigestRunResult has defaults."""
        r = PortfolioAlertEmailDigestRunResult()
        assert r.draft is None
        assert r.warnings == []


# ---------------------------------------------------------------------------
# Integration test with focus items
# ---------------------------------------------------------------------------

class TestWithFocusItems:
    """Integration tests with actual focus items."""

    def test_digest_with_csv_items(self):
        """Digest built from CSV includes sections."""
        with tempfile.TemporaryDirectory() as tmp:
            _create_test_digest_csv(tmp)
            draft = build_portfolio_alert_email_digest(
                exports_dir=tmp,
            )
            assert draft.focus_item_count >= 1
            assert draft.high_count >= 1
            # Should have sections for severity, etc
            assert len(draft.sections) >= 1
            # Subject should mention counts
            assert "item" in draft.subject.lower()

    def test_export_with_csv_items(self):
        """Export with CSV items produces populated files."""
        with tempfile.TemporaryDirectory() as tmp:
            _create_test_digest_csv(tmp)
            result = export_portfolio_alert_email_digest(
                exports_dir=tmp,
                output_dir=tmp,
                fmt="both",
            )
            assert result.focus_item_count >= 1
            # Read the txt file and check content
            txt_paths = [
                p for p in result.output_paths
                if p.endswith(".txt")
            ]
            assert len(txt_paths) == 1
            content = Path(txt_paths[0]).read_text(
                encoding="utf-8"
            )
            assert "HIGH SEVERITY" in content or (
                "ALERT COUNTS" in content
            )
