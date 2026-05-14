"""Tests for Milestone 50: Release Candidate Finalization.

Tests version metadata, release artifact inventory, readiness
checks, manual GitHub commands, report build, Markdown/CSV
export, final release notes generation, CLI commands, dashboard,
and guard-rails.
"""

import csv
import io
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from marketsentry.release_finalization import (
    ManualReleaseCommand,
    ReleaseArtifactInventoryItem,
    ReleaseFinalizationReport,
    ReleaseFinalizationRunResult,
    ReleaseReadinessCheck,
    ReleaseVersionMetadata,
    build_manual_github_release_commands,
    build_release_artifact_inventory,
    build_release_finalization_report,
    build_release_readiness_checks,
    build_release_version_metadata,
    export_release_finalization_report,
)

runner = CliRunner()


# -------------------------------------------------------------------
# Version metadata tests
# -------------------------------------------------------------------


class TestVersionMetadata:
    """Test version metadata building."""

    def test_metadata_builds(self):
        """Version metadata builds successfully."""
        meta = build_release_version_metadata()
        assert isinstance(meta, ReleaseVersionMetadata)
        assert meta.version == "0.1.0-rc1"
        assert meta.generated_at != ""

    def test_metadata_has_required_fields(self):
        """Metadata has all required fields."""
        meta = build_release_version_metadata()
        assert meta.version
        assert meta.repository_url
        assert meta.package_name == "marketsentry"
        assert meta.python_target == "3.11+"
        assert meta.local_only_status == "local_only"
        assert meta.release_candidate_status == "rc1"

    def test_metadata_custom_version(self):
        """Metadata accepts custom version."""
        meta = build_release_version_metadata(
            version="1.0.0"
        )
        assert meta.version == "1.0.0"

    def test_metadata_reads_git_commit(self):
        """Metadata reads local git commit."""
        meta = build_release_version_metadata()
        assert meta.commit != ""

    def test_metadata_unknown_git_graceful(self):
        """Metadata gracefully handles missing git."""
        with patch(
            "marketsentry.release_finalization"
            ".subprocess.run",
            side_effect=FileNotFoundError(
                "git not found"
            ),
        ):
            meta = build_release_version_metadata()
        assert meta.commit == "unknown"
        assert meta.branch == "unknown"

    def test_version_in_init(self):
        """__version__ exists in __init__.py."""
        from marketsentry import __version__

        assert __version__
        assert "0.1.0" in __version__


# -------------------------------------------------------------------
# Artifact inventory tests
# -------------------------------------------------------------------


class TestArtifactInventory:
    """Test release artifact inventory."""

    def test_inventory_builds(self):
        """Artifact inventory builds a non-empty list."""
        items = build_release_artifact_inventory()
        assert len(items) > 0

    def test_inventory_items_have_fields(self):
        """Each artifact item has required fields."""
        items = build_release_artifact_inventory()
        for item in items:
            assert isinstance(
                item, ReleaseArtifactInventoryItem
            )
            assert item.path
            assert item.artifact_type
            assert item.notes

    def test_inventory_detects_existing_files(self):
        """Inventory correctly detects existing files."""
        items = build_release_artifact_inventory()
        readme = next(
            (i for i in items if i.path == "README.md"),
            None,
        )
        assert readme is not None
        assert readme.exists is True

    def test_inventory_detects_missing_files(self):
        """Inventory detects missing files in temp dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            items = build_release_artifact_inventory(
                project_root=tmpdir
            )
            readme = next(
                (
                    i
                    for i in items
                    if i.path == "README.md"
                ),
                None,
            )
            assert readme is not None
            assert readme.exists is False

    def test_inventory_includes_key_artifacts(self):
        """Inventory includes expected artifacts."""
        items = build_release_artifact_inventory()
        paths = {i.path for i in items}
        assert "PRD.md" in paths
        assert "Architecture.md" in paths
        assert "README.md" in paths
        assert "docs/RUNBOOK.md" in paths
        assert "requirements.txt" in paths
        assert "pyproject.toml" in paths
        assert "src/marketsentry/" in paths
        assert "tests/" in paths
        assert "scripts/" in paths


# -------------------------------------------------------------------
# Readiness checks tests
# -------------------------------------------------------------------


class TestReadinessChecks:
    """Test release readiness checks."""

    def test_readiness_builds(self):
        """Readiness checks build a non-empty list."""
        checks = build_release_readiness_checks()
        assert len(checks) > 0

    def test_readiness_items_have_fields(self):
        """Each readiness check has required fields."""
        checks = build_release_readiness_checks()
        for check in checks:
            assert isinstance(
                check, ReleaseReadinessCheck
            )
            assert check.check_id
            assert check.status in (
                "pass", "warning", "fail",
                "not_checked",
            )

    def test_readiness_script_safety(self):
        """Script safety checks pass."""
        checks = build_release_readiness_checks()
        force_live = next(
            (
                c for c in checks
                if c.check_id == "no_force_live_in_scripts"
            ),
            None,
        )
        assert force_live is not None
        assert force_live.status == "pass"

    def test_readiness_no_browser_automation(self):
        """Browser automation check passes."""
        checks = build_release_readiness_checks()
        browser = next(
            (
                c for c in checks
                if c.check_id == "no_browser_automation"
            ),
            None,
        )
        assert browser is not None
        assert browser.status == "pass"

    def test_readiness_no_walkability(self):
        """Walkability check passes."""
        checks = build_release_readiness_checks()
        walk = next(
            (
                c for c in checks
                if c.check_id == "no_walkability_fields"
            ),
            None,
        )
        assert walk is not None
        assert walk.status == "pass"

    def test_readiness_version_metadata(self):
        """Version metadata check passes."""
        checks = build_release_readiness_checks()
        ver = next(
            (
                c for c in checks
                if c.check_id == "version_metadata_exists"
            ),
            None,
        )
        assert ver is not None
        assert ver.status == "pass"

    def test_readiness_no_auto_github_release(self):
        """No automatic GitHub release check passes."""
        checks = build_release_readiness_checks()
        gh = next(
            (
                c for c in checks
                if c.check_id == "no_auto_github_release"
            ),
            None,
        )
        assert gh is not None
        assert gh.status == "pass"


# -------------------------------------------------------------------
# Manual commands tests
# -------------------------------------------------------------------


class TestManualCommands:
    """Test manual GitHub release commands."""

    def test_commands_generated(self):
        """Manual commands are generated."""
        commands = build_manual_github_release_commands()
        assert len(commands) > 0

    def test_commands_not_executed(self):
        """All commands have executed=False."""
        commands = build_manual_github_release_commands()
        for cmd in commands:
            assert isinstance(cmd, ManualReleaseCommand)
            assert cmd.executed is False

    def test_commands_include_tag(self):
        """Commands include git tag creation."""
        commands = build_manual_github_release_commands()
        tag_cmds = [
            c for c in commands
            if "git tag" in c.command
        ]
        assert len(tag_cmds) > 0

    def test_commands_include_push(self):
        """Commands include tag push."""
        commands = build_manual_github_release_commands()
        push_cmds = [
            c for c in commands
            if "git push" in c.command
        ]
        assert len(push_cmds) > 0

    def test_commands_include_gh_release(self):
        """Commands include gh release create."""
        commands = build_manual_github_release_commands()
        gh_cmds = [
            c for c in commands
            if "gh release create" in c.command
        ]
        assert len(gh_cmds) > 0

    def test_commands_use_version(self):
        """Commands use correct version string."""
        commands = build_manual_github_release_commands(
            version="2.0.0"
        )
        tag_cmds = [
            c for c in commands
            if "v2.0.0" in c.command
        ]
        assert len(tag_cmds) > 0

    def test_no_git_tag_actually_executed(self):
        """Verify no git tag was created by module."""
        result = subprocess.run(
            ["git", "tag", "-l", "v0.1.0-rc1"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert "v0.1.0-rc1" not in result.stdout

    def test_no_gh_release_actually_executed(self):
        """Verify no gh release was created by module.

        The module generates commands but does not run
        them. This test verifies no subprocess.run was
        called with gh release create.
        """
        # The module only uses subprocess for git
        # rev-parse, never for git tag or gh release.
        source = Path(
            "src/marketsentry/release_finalization.py"
        ).read_text(encoding="utf-8")
        assert 'subprocess.run(["git", "tag"' not in source
        assert (
            'subprocess.run(["gh", "release"'
            not in source
        )


# -------------------------------------------------------------------
# Report build tests
# -------------------------------------------------------------------


class TestReportBuild:
    """Test release finalization report building."""

    def test_report_builds(self):
        """Finalization report builds successfully."""
        result = build_release_finalization_report()
        assert isinstance(
            result, ReleaseFinalizationRunResult
        )

    def test_report_has_metadata(self):
        """Report includes version metadata."""
        result = build_release_finalization_report()
        assert (
            result.report.version_metadata.version
            == "0.1.0-rc1"
        )

    def test_report_has_artifacts(self):
        """Report includes artifact inventory."""
        result = build_release_finalization_report()
        assert result.artifact_count > 0
        assert result.artifact_present > 0

    def test_report_has_readiness(self):
        """Report includes readiness checks."""
        result = build_release_finalization_report()
        assert len(result.report.readiness_checks) > 0
        assert result.readiness_pass > 0

    def test_report_has_commands(self):
        """Report includes manual commands."""
        result = build_release_finalization_report()
        assert result.command_count > 0


# -------------------------------------------------------------------
# Export tests
# -------------------------------------------------------------------


class TestExport:
    """Test release finalization report export."""

    def test_markdown_export(self):
        """Markdown report exports successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_release_finalization_report()
            exported = export_release_finalization_report(
                result,
                output_dir=tmpdir,
                fmt="md",
                project_root=tmpdir,
            )
            md_files = list(
                Path(tmpdir).glob(
                    "release_finalization_*.md"
                )
            )
            assert len(md_files) >= 1
            content = md_files[0].read_text(
                encoding="utf-8"
            )
            assert (
                "Release Finalization Report" in content
            )
            assert "Version Metadata" in content
            assert "Artifact Inventory" in content
            assert "Readiness Checks" in content
            assert "Manual GitHub Release" in content
            assert "Safety Note" in content
            assert "NOT executed" in content

    def test_csv_export(self):
        """CSV report exports successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_release_finalization_report()
            exported = export_release_finalization_report(
                result,
                output_dir=tmpdir,
                fmt="csv",
                project_root=tmpdir,
            )
            csv_files = list(
                Path(tmpdir).glob(
                    "release_finalization_*.csv"
                )
            )
            assert len(csv_files) >= 1
            content = csv_files[0].read_text(
                encoding="utf-8"
            )
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)
            assert len(rows) > 1
            header = rows[0]
            assert "section" in header
            assert "item_id" in header
            assert "status" in header
            assert "path_or_command" in header

    def test_both_export(self):
        """Both MD and CSV export together."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_release_finalization_report()
            exported = export_release_finalization_report(
                result,
                output_dir=tmpdir,
                fmt="both",
                project_root=tmpdir,
            )
            md_files = list(
                Path(tmpdir).glob(
                    "release_finalization_*.md"
                )
            )
            csv_files = list(
                Path(tmpdir).glob(
                    "release_finalization_*.csv"
                )
            )
            assert len(md_files) >= 1
            assert len(csv_files) >= 1

    def test_release_notes_final_generated(self):
        """docs/RELEASE_NOTES_FINAL.md generated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_release_finalization_report()
            exported = export_release_finalization_report(
                result,
                output_dir=tmpdir,
                fmt="both",
                project_root=tmpdir,
            )
            notes_path = (
                Path(tmpdir) / "docs"
                / "RELEASE_NOTES_FINAL.md"
            )
            assert notes_path.exists()
            content = notes_path.read_text(
                encoding="utf-8"
            )
            assert "Market_Sentry" in content
            assert "0.1.0-rc1" in content
            assert "Safety Guarantees" in content
            assert "Major Capabilities" in content
            assert "Known Limitations" in content
            assert "Manual Release Checklist" in content

    def test_output_paths_populated(self):
        """Export populates output_paths on result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_release_finalization_report()
            exported = export_release_finalization_report(
                result,
                output_dir=tmpdir,
                fmt="both",
                project_root=tmpdir,
            )
            assert (
                len(exported.report.output_paths) >= 3
            )
            paths = exported.report.output_paths
            assert any(
                "release_finalization" in p
                and p.endswith(".md")
                for p in paths
            )
            assert any(
                "release_finalization" in p
                and p.endswith(".csv")
                for p in paths
            )
            assert any(
                "RELEASE_NOTES_FINAL" in p
                for p in paths
            )


# -------------------------------------------------------------------
# CLI tests
# -------------------------------------------------------------------


class TestCLI:
    """Test CLI commands."""

    def test_release_finalization_summary(self):
        """CLI release-finalization-summary runs."""
        from marketsentry.cli import app

        result = runner.invoke(
            app,
            ["release-finalization-summary"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert (
            "Release Finalization Summary" in result.output
        )
        assert "No GitHub release" in result.output

    def test_export_release_finalization_report(self):
        """CLI export-release-finalization-report runs."""
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                app,
                [
                    "export-release-finalization-report",
                    "--output-dir",
                    tmpdir,
                    "--format",
                    "both",
                ],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert (
                "Release Finalization Report Export"
                in result.output
            )
            assert "Exported" in result.output

    def test_release_manual_github_commands(self):
        """CLI release-manual-github-commands runs."""
        from marketsentry.cli import app

        result = runner.invoke(
            app,
            ["release-manual-github-commands"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert (
            "Manual GitHub Release Commands"
            in result.output
        )
        assert "NOT executed" in result.output
        assert "git tag" in result.output


# -------------------------------------------------------------------
# Dashboard tests
# -------------------------------------------------------------------


class TestDashboard:
    """Test dashboard integration."""

    def test_dashboard_finalization_data_loads(self):
        """Dashboard can import and build report."""
        from marketsentry.release_finalization import (
            build_release_finalization_report as _build,
        )

        result = _build()
        assert isinstance(
            result, ReleaseFinalizationRunResult
        )

    def test_dashboard_has_finalization_section(self):
        """Dashboard app contains finalization section."""
        source = Path(
            "src/marketsentry/dashboard_app.py"
        ).read_text(encoding="utf-8")
        assert "Release Finalization" in source
        assert (
            "build_release_finalization_report" in source
        )
        assert "Readiness Pass" in source
        assert "Artifacts Present" in source
        assert "Manual Commands" in source


# -------------------------------------------------------------------
# Scheduled script safety tests
# -------------------------------------------------------------------


class TestScheduledScriptSafety:
    """Scheduled scripts do not include finalization."""

    def test_no_finalization_in_scripts(self):
        """No scheduled script invokes finalization."""
        scripts_path = Path("scripts")
        if scripts_path.exists():
            for ext in ("*.bat", "*.ps1"):
                for sf in scripts_path.glob(ext):
                    content = sf.read_text(
                        encoding="utf-8"
                    )
                    assert (
                        "release-finalization"
                        not in content.lower()
                    )
                    assert (
                        "release-manual-github"
                        not in content.lower()
                    )


# -------------------------------------------------------------------
# Safety guard-rail tests
# -------------------------------------------------------------------


class TestNoOutboundNotifications:
    """No outbound notification code added."""

    def test_module_no_smtplib(self):
        """Module does not import smtplib."""
        import marketsentry.release_finalization as mod

        assert not hasattr(mod, "smtplib")

    def test_module_no_smtp_connection(self):
        """Module does not contain SMTP connection code."""
        source = Path(
            "src/marketsentry/release_finalization.py"
        ).read_text(encoding="utf-8")
        assert "SMTP(" not in source
        assert "smtp.connect" not in source
        assert "smtp.send" not in source

    def test_module_no_gmail_outlook(self):
        """Module does not integrate with Gmail/Outlook."""
        source = Path(
            "src/marketsentry/release_finalization.py"
        ).read_text(encoding="utf-8")
        assert "GmailAPI" not in source
        assert "OutlookClient" not in source

    def test_module_no_webhook_imports(self):
        """Module does not import HTTP request libs."""
        import marketsentry.release_finalization as mod

        assert not hasattr(mod, "requests")
        assert not hasattr(mod, "httpx")

    def test_module_no_credential_storage(self):
        """Module does not store credentials."""
        source = Path(
            "src/marketsentry/release_finalization.py"
        ).read_text(encoding="utf-8")
        assert "getpass" not in source
        assert "keyring" not in source

    def test_module_no_sms(self):
        """Module does not import SMS libraries."""
        import marketsentry.release_finalization as mod

        assert not hasattr(mod, "twilio")


class TestNoMutation:
    """No candidate/watchlist/alert state mutation."""

    def test_no_candidate_mutation(self):
        """Module does not mutate candidates."""
        source = Path(
            "src/marketsentry/release_finalization.py"
        ).read_text(encoding="utf-8")
        assert "promote_candidate" not in source
        assert "reject_candidate" not in source
        assert "save_candidate" not in source

    def test_no_watchlist_mutation(self):
        """Module does not mutate watchlist."""
        source = Path(
            "src/marketsentry/release_finalization.py"
        ).read_text(encoding="utf-8")
        assert "add_to_watchlist" not in source
        assert "remove_from_watchlist" not in source

    def test_no_alert_mutation(self):
        """Module does not mutate alert status."""
        source = Path(
            "src/marketsentry/release_finalization.py"
        ).read_text(encoding="utf-8")
        assert "acknowledge_alert" not in source
        assert "resolve_alert" not in source
        assert "archive_alert" not in source

    def test_no_write_operations(self):
        """Module does not perform database writes."""
        source = Path(
            "src/marketsentry/release_finalization.py"
        ).read_text(encoding="utf-8")
        assert "INSERT INTO" not in source
        assert "DELETE FROM" not in source
        assert "CREATE TABLE" not in source


class TestNoRedfinOverwrite:
    """No Redfin source-of-truth overwrite."""

    def test_no_redfin_sot_overwrite(self):
        """Module does not overwrite Redfin SOT fields."""
        import marketsentry.release_finalization as mod

        assert not hasattr(
            mod, "redfin_source_of_truth"
        )
        assert not hasattr(mod, "overwrite_redfin_sot")


class TestQuietGatekeeper:
    """Quiet Score gatekeeper unchanged."""

    def test_no_quiet_threshold_change(self):
        """Module does not modify Quiet Score threshold."""
        import marketsentry.release_finalization as mod

        assert not hasattr(mod, "QUIET_THRESHOLD")
        assert not hasattr(mod, "quiet_threshold")


class TestNoWalkability:
    """No walkability fields added."""

    def test_no_walkability_fields(self):
        """Module has no walkability attributes."""
        import marketsentry.release_finalization as mod

        assert not hasattr(mod, "walkability_score")
        assert not hasattr(mod, "walk_score")
        assert not hasattr(mod, "walkability_rating")


class TestNoBrowserAutomation:
    """No browser automation added."""

    def test_no_playwright_import(self):
        """Module does not import playwright."""
        import marketsentry.release_finalization as mod

        assert not hasattr(mod, "playwright")

    def test_no_selenium_import(self):
        """Module does not import selenium."""
        import marketsentry.release_finalization as mod

        assert not hasattr(mod, "selenium")


class TestNoNetworkCalls:
    """No real network calls in tests."""

    def test_no_requests_import(self):
        """Module does not import requests library."""
        import marketsentry.release_finalization as mod

        assert not hasattr(mod, "requests")

    def test_no_httpx_import(self):
        """Module does not import httpx library."""
        import marketsentry.release_finalization as mod

        assert not hasattr(mod, "httpx")


class TestNoGitHubRelease:
    """No GitHub release or tag created automatically."""

    def test_no_github_api_calls(self):
        """Module does not call GitHub API."""
        source = Path(
            "src/marketsentry/release_finalization.py"
        ).read_text(encoding="utf-8")
        assert "api.github.com" not in source

    def test_no_git_tag_execution(self):
        """Module does not execute git tag."""
        source = Path(
            "src/marketsentry/release_finalization.py"
        ).read_text(encoding="utf-8")
        # Module uses subprocess only for rev-parse
        assert (
            'subprocess.run(["git", "tag"' not in source
        )
        assert (
            'subprocess.run(["git", "push"' not in source
        )

    def test_no_gh_release_execution(self):
        """Module does not execute gh release."""
        source = Path(
            "src/marketsentry/release_finalization.py"
        ).read_text(encoding="utf-8")
        assert (
            'subprocess.run(["gh"' not in source
        )


# -------------------------------------------------------------------
# Model tests
# -------------------------------------------------------------------


class TestModels:
    """Test Pydantic model construction."""

    def test_version_metadata_model(self):
        """ReleaseVersionMetadata constructs."""
        meta = ReleaseVersionMetadata()
        assert meta.version == "0.1.0-rc1"
        assert meta.local_only_status == "local_only"

    def test_readiness_check_model(self):
        """ReleaseReadinessCheck constructs."""
        check = ReleaseReadinessCheck(
            check_id="test_check",
            status="pass",
            detail="OK",
        )
        assert check.check_id == "test_check"
        assert check.status == "pass"

    def test_artifact_item_model(self):
        """ReleaseArtifactInventoryItem constructs."""
        item = ReleaseArtifactInventoryItem(
            path="test.md",
            exists=True,
            artifact_type="documentation",
            notes="Test file",
        )
        assert item.path == "test.md"
        assert item.exists is True

    def test_manual_command_model(self):
        """ManualReleaseCommand constructs."""
        cmd = ManualReleaseCommand(
            step=1,
            command="git status",
            description="Check status",
            executed=False,
        )
        assert cmd.step == 1
        assert cmd.executed is False

    def test_report_model(self):
        """ReleaseFinalizationReport constructs."""
        report = ReleaseFinalizationReport()
        assert report.artifacts == []
        assert report.readiness_checks == []
        assert report.manual_commands == []
        assert report.output_paths == []

    def test_run_result_model(self):
        """ReleaseFinalizationRunResult constructs."""
        result = ReleaseFinalizationRunResult()
        assert result.readiness_pass == 0
        assert result.readiness_fail == 0
        assert result.artifact_count == 0
        assert result.command_count == 0
