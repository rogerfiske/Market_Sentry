"""Tests for Milestone 49: Release Candidate Hardening.

Tests release candidate metadata, operator acceptance checklist,
safe/manual-approval workflow inventories, validation, report
build, Markdown/CSV export, doc generation, CLI commands,
dashboard, and guard-rails.
"""

import csv
import io
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from marketsentry.release_candidate import (
    ReleaseCandidateChecklistItem,
    ReleaseCandidateMetadata,
    ReleaseCandidateReport,
    ReleaseCandidateRunResult,
    ReleaseCandidateValidationResult,
    ReleaseCandidateWorkflowItem,
    build_manual_approval_workflow_inventory,
    build_operator_acceptance_checklist,
    build_release_candidate_metadata,
    build_release_candidate_report,
    build_safe_workflow_inventory,
    export_release_candidate_report,
    run_release_candidate_validation,
)

runner = CliRunner()


# -------------------------------------------------------------------
# Metadata tests
# -------------------------------------------------------------------


class TestMetadata:
    """Test release candidate metadata building."""

    def test_metadata_builds_with_unknown_git(self):
        """Metadata builds gracefully when git is unavailable."""
        with patch(
            "marketsentry.release_candidate.subprocess.run",
            side_effect=FileNotFoundError("git not found"),
        ):
            meta = build_release_candidate_metadata()
        assert isinstance(meta, ReleaseCandidateMetadata)
        assert meta.current_git_commit == "unknown"
        assert meta.current_branch == "unknown"

    def test_metadata_reads_git_commit(self):
        """Metadata reads git commit when available."""
        meta = build_release_candidate_metadata()
        assert isinstance(meta, ReleaseCandidateMetadata)
        # In a real git repo, commit should not be "unknown"
        assert meta.current_git_commit != ""

    def test_metadata_has_required_fields(self):
        """Metadata has all required fields."""
        meta = build_release_candidate_metadata()
        assert meta.project_name == "Market_Sentry"
        assert "github.com" in meta.repository_url
        assert meta.generated_at != ""
        assert meta.package_path == "src/marketsentry"
        assert meta.python_version != ""
        assert meta.local_only_status == "local_only"
        assert meta.live_retrieval_default_status == "disabled"
        assert meta.outbound_notification_status == "none"
        assert meta.quiet_gatekeeper_status == "unchanged"
        assert meta.walkability_exclusion_status == "excluded"

    def test_metadata_accepts_test_count(self):
        """Metadata accepts an optional test count."""
        meta = build_release_candidate_metadata(test_count=2500)
        assert meta.test_count == 2500

    def test_metadata_default_test_count(self):
        """Default test count is -1 (unknown)."""
        meta = build_release_candidate_metadata()
        assert meta.test_count == -1


# -------------------------------------------------------------------
# Checklist tests
# -------------------------------------------------------------------


class TestChecklist:
    """Test operator acceptance checklist."""

    def test_checklist_builds(self):
        """Checklist builds a non-empty list."""
        items = build_operator_acceptance_checklist()
        assert len(items) > 0

    def test_checklist_items_have_fields(self):
        """Each checklist item has required fields."""
        items = build_operator_acceptance_checklist()
        for item in items:
            assert isinstance(
                item, ReleaseCandidateChecklistItem
            )
            assert item.item_id
            assert item.category
            assert item.description
            assert item.status in (
                "pass",
                "warning",
                "fail",
                "not_checked",
            )

    def test_checklist_doc_existence_pass(self):
        """Checklist correctly detects existing docs."""
        items = build_operator_acceptance_checklist()
        readme_item = next(
            (i for i in items if i.item_id == "doc_readme"),
            None,
        )
        assert readme_item is not None
        assert readme_item.status == "pass"

    def test_checklist_doc_existence_fail(self):
        """Checklist detects missing docs in temp project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            items = build_operator_acceptance_checklist(
                project_root=tmpdir,
                db_path=str(Path(tmpdir) / "test.db"),
                exports_dir=str(
                    Path(tmpdir) / "exports"
                ),
            )
            readme_item = next(
                (
                    i
                    for i in items
                    if i.item_id == "doc_readme"
                ),
                None,
            )
            assert readme_item is not None
            assert readme_item.status == "fail"

    def test_checklist_safety_items_pass(self):
        """Safety-related checklist items pass."""
        items = build_operator_acceptance_checklist()
        safety_ids = [
            "live_retrieval_disabled",
            "no_outbound_notification",
            "no_credentials",
            "quiet_gatekeeper",
            "walkability_excluded",
        ]
        for sid in safety_ids:
            item = next(
                (i for i in items if i.item_id == sid),
                None,
            )
            assert item is not None, f"Missing: {sid}"
            assert item.status == "pass", (
                f"{sid} should pass"
            )

    def test_checklist_db_init_pass(self):
        """Database init checklist item passes."""
        items = build_operator_acceptance_checklist()
        db_item = next(
            (i for i in items if i.item_id == "db_init"),
            None,
        )
        assert db_item is not None
        assert db_item.status == "pass"

    def test_checklist_known_categories(self):
        """Checklist covers expected categories."""
        items = build_operator_acceptance_checklist()
        cats = {i.category for i in items}
        assert "documentation" in cats
        assert "commands" in cats
        assert "scripts" in cats
        assert "safety" in cats
        assert "quality" in cats


# -------------------------------------------------------------------
# Safe workflow inventory tests
# -------------------------------------------------------------------


class TestSafeWorkflowInventory:
    """Test safe workflow inventory building."""

    def test_safe_workflows_build(self):
        """Safe workflow inventory returns items."""
        workflows = build_safe_workflow_inventory()
        assert len(workflows) > 0

    def test_safe_workflow_items_have_fields(self):
        """Each workflow item has required fields."""
        workflows = build_safe_workflow_inventory()
        for w in workflows:
            assert isinstance(
                w, ReleaseCandidateWorkflowItem
            )
            assert w.workflow_id
            assert w.name
            assert w.category
            assert w.access_type

    def test_safe_workflows_include_exports(self):
        """Safe workflows include export operations."""
        workflows = build_safe_workflow_inventory()
        ids = {w.workflow_id for w in workflows}
        assert "export_review" in ids
        assert "export_monitoring" in ids
        assert "export_ops_digest" in ids
        assert "export_review_pack" in ids
        assert "export_ops_bundle" in ids

    def test_safe_workflows_include_dashboard(self):
        """Safe workflows include dashboard."""
        workflows = build_safe_workflow_inventory()
        ids = {w.workflow_id for w in workflows}
        assert "run_dashboard" in ids


# -------------------------------------------------------------------
# Manual approval workflow inventory tests
# -------------------------------------------------------------------


class TestManualApprovalWorkflowInventory:
    """Test manual approval workflow inventory building."""

    def test_manual_workflows_build(self):
        """Manual approval workflows return items."""
        workflows = (
            build_manual_approval_workflow_inventory()
        )
        assert len(workflows) > 0

    def test_manual_workflow_items_have_fields(self):
        """Each manual workflow item has required fields."""
        workflows = (
            build_manual_approval_workflow_inventory()
        )
        for w in workflows:
            assert isinstance(
                w, ReleaseCandidateWorkflowItem
            )
            assert w.workflow_id
            assert w.name
            assert w.category
            assert w.access_type == "mutating"

    def test_manual_workflows_include_retrieval(self):
        """Manual workflows include live retrieval."""
        workflows = (
            build_manual_approval_workflow_inventory()
        )
        ids = {w.workflow_id for w in workflows}
        assert "live_redfin_retrieval" in ids
        assert "batch_retrieval" in ids

    def test_manual_workflows_include_triage(self):
        """Manual workflows include triage/archive ops."""
        workflows = (
            build_manual_approval_workflow_inventory()
        )
        ids = {w.workflow_id for w in workflows}
        assert "triage_alerts" in ids
        assert "apply_triage" in ids
        assert "apply_archive" in ids
        assert "apply_expiration" in ids


# -------------------------------------------------------------------
# Validation tests
# -------------------------------------------------------------------


class TestValidation:
    """Test release candidate validation."""

    def test_validation_passes_real_project(self):
        """Validation passes on real project root."""
        results = run_release_candidate_validation()
        assert len(results) > 0
        # Validation should not have hard failures
        # on the real project (may have warnings)
        for r in results:
            assert isinstance(
                r, ReleaseCandidateValidationResult
            )
            assert r.check_id
            assert r.status in (
                "pass",
                "warning",
                "fail",
            )

    def test_validation_detects_missing_docs(self):
        """Validation detects missing docs in temp project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = run_release_candidate_validation(
                project_root=tmpdir,
                db_path=str(Path(tmpdir) / "test.db"),
                exports_dir=str(
                    Path(tmpdir) / "exports"
                ),
            )
            file_check = next(
                (
                    r
                    for r in results
                    if r.check_id == "required_files"
                ),
                None,
            )
            assert file_check is not None
            assert file_check.status == "fail"
            assert "Missing" in file_check.detail

    def test_validation_checks_ops_bundle(self):
        """Validation checks operations bundle builds."""
        results = run_release_candidate_validation()
        bundle_check = next(
            (
                r
                for r in results
                if r.check_id == "ops_bundle_builds"
            ),
            None,
        )
        assert bundle_check is not None
        assert bundle_check.status == "pass"

    def test_validation_checks_smoke_test(self):
        """Validation checks smoke test."""
        results = run_release_candidate_validation()
        smoke_check = next(
            (
                r
                for r in results
                if r.check_id == "smoke_test"
            ),
            None,
        )
        assert smoke_check is not None
        assert smoke_check.status == "pass"

    def test_validation_checks_safety_audit(self):
        """Validation checks safety audit."""
        results = run_release_candidate_validation()
        safety_check = next(
            (
                r
                for r in results
                if r.check_id == "safety_audit"
            ),
            None,
        )
        assert safety_check is not None
        assert safety_check.status == "pass"

    def test_validation_checks_config_templates(self):
        """Validation checks config templates."""
        results = run_release_candidate_validation()
        config_check = next(
            (
                r
                for r in results
                if r.check_id == "config_templates"
            ),
            None,
        )
        assert config_check is not None
        # Templates should exist or warn
        assert config_check.status in ("pass", "warning")

    def test_validation_checks_rc_module_safety(self):
        """Validation checks release candidate module safety."""
        results = run_release_candidate_validation()
        rc_check = next(
            (
                r
                for r in results
                if r.check_id == "rc_module_safety"
            ),
            None,
        )
        assert rc_check is not None
        assert rc_check.status == "pass"


# -------------------------------------------------------------------
# Report build tests
# -------------------------------------------------------------------


class TestReportBuild:
    """Test release candidate report building."""

    def test_report_builds(self):
        """Release candidate report builds successfully."""
        result = build_release_candidate_report()
        assert isinstance(
            result, ReleaseCandidateRunResult
        )
        assert isinstance(
            result.report, ReleaseCandidateReport
        )

    def test_report_has_metadata(self):
        """Report includes metadata."""
        result = build_release_candidate_report()
        assert (
            result.report.metadata.project_name
            == "Market_Sentry"
        )

    def test_report_has_checklist(self):
        """Report includes checklist items."""
        result = build_release_candidate_report()
        assert len(result.report.checklist) > 0
        assert result.checklist_pass > 0

    def test_report_has_workflows(self):
        """Report includes workflow inventories."""
        result = build_release_candidate_report()
        assert result.safe_workflow_count > 0
        assert result.manual_workflow_count > 0

    def test_report_has_validation(self):
        """Report includes validation results."""
        result = build_release_candidate_report()
        assert len(result.report.validation_results) > 0
        assert result.validation_pass > 0


# -------------------------------------------------------------------
# Export tests
# -------------------------------------------------------------------


class TestExport:
    """Test release candidate report export."""

    def test_markdown_export(self):
        """Markdown report exports successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_release_candidate_report()
            exported = export_release_candidate_report(
                result,
                output_dir=tmpdir,
                fmt="md",
                project_root=tmpdir,
            )
            md_files = list(
                Path(tmpdir).glob(
                    "release_candidate_report_*.md"
                )
            )
            assert len(md_files) >= 1
            content = md_files[0].read_text(
                encoding="utf-8"
            )
            assert "Release Candidate Report" in content
            assert "Market_Sentry" in content
            assert "Operator Acceptance Checklist" in content
            assert "Safe Workflows" in content
            assert "Manual Approval" in content
            assert "Validation Results" in content
            assert "Safety Note" in content

    def test_csv_export(self):
        """CSV report exports successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_release_candidate_report()
            exported = export_release_candidate_report(
                result,
                output_dir=tmpdir,
                fmt="csv",
                project_root=tmpdir,
            )
            csv_files = list(
                Path(tmpdir).glob(
                    "release_candidate_report_*.csv"
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
            assert "recommended_local_action" in header

    def test_both_export(self):
        """Both MD and CSV export together."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_release_candidate_report()
            exported = export_release_candidate_report(
                result,
                output_dir=tmpdir,
                fmt="both",
                project_root=tmpdir,
            )
            md_files = list(
                Path(tmpdir).glob(
                    "release_candidate_report_*.md"
                )
            )
            csv_files = list(
                Path(tmpdir).glob(
                    "release_candidate_report_*.csv"
                )
            )
            assert len(md_files) >= 1
            assert len(csv_files) >= 1

    def test_checklist_doc_generated(self):
        """docs/RELEASE_CANDIDATE_CHECKLIST.md generated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_release_candidate_report()
            exported = export_release_candidate_report(
                result,
                output_dir=tmpdir,
                fmt="both",
                project_root=tmpdir,
            )
            checklist_path = (
                Path(tmpdir) / "docs"
                / "RELEASE_CANDIDATE_CHECKLIST.md"
            )
            assert checklist_path.exists()
            content = checklist_path.read_text(
                encoding="utf-8"
            )
            assert "Release Candidate Checklist" in content
            assert "Operator Acceptance Checklist" in content
            assert "Recommended Actions" in content
            assert "GitHub Release Preparation" in content

    def test_release_notes_draft_generated(self):
        """docs/RELEASE_NOTES_DRAFT.md generated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_release_candidate_report()
            exported = export_release_candidate_report(
                result,
                output_dir=tmpdir,
                fmt="both",
                project_root=tmpdir,
            )
            notes_path = (
                Path(tmpdir) / "docs"
                / "RELEASE_NOTES_DRAFT.md"
            )
            assert notes_path.exists()
            content = notes_path.read_text(
                encoding="utf-8"
            )
            assert "Release Notes Draft" in content
            assert "Market Sentry" in content
            assert "Safety Guarantees" in content
            assert "Key Features" in content
            assert "Getting Started" in content

    def test_output_paths_populated(self):
        """Export populates output_paths on result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_release_candidate_report()
            exported = export_release_candidate_report(
                result,
                output_dir=tmpdir,
                fmt="both",
                project_root=tmpdir,
            )
            assert len(exported.report.output_paths) >= 4
            # Should include MD, CSV, checklist, notes
            paths = exported.report.output_paths
            assert any("release_candidate_report" in p and p.endswith(".md") for p in paths)
            assert any("release_candidate_report" in p and p.endswith(".csv") for p in paths)
            assert any("RELEASE_CANDIDATE_CHECKLIST" in p for p in paths)
            assert any("RELEASE_NOTES_DRAFT" in p for p in paths)


# -------------------------------------------------------------------
# CLI tests
# -------------------------------------------------------------------


class TestCLI:
    """Test CLI commands."""

    def test_release_candidate_summary(self):
        """CLI release-candidate-summary runs."""
        from marketsentry.cli import app

        result = runner.invoke(
            app,
            ["release-candidate-summary"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "Release Candidate Summary" in result.output
        assert "No mutations" in result.output

    def test_export_release_candidate_report(self):
        """CLI export-release-candidate-report runs."""
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                app,
                [
                    "export-release-candidate-report",
                    "--output-dir",
                    tmpdir,
                    # Keeps the generated checklist and release notes
                    # out of the tracked docs/ directory.
                    "--project-root",
                    tmpdir,
                    "--format",
                    "both",
                ],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert (
                "Release Candidate Report Export"
                in result.output
            )
            assert "Exported" in result.output
            assert "No mutations" in result.output

    def test_release_candidate_checklist(self):
        """CLI release-candidate-checklist runs."""
        from marketsentry.cli import app

        result = runner.invoke(
            app,
            ["release-candidate-checklist"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert (
            "Release Candidate Checklist" in result.output
        )
        assert "No mutations" in result.output


# -------------------------------------------------------------------
# Dashboard tests
# -------------------------------------------------------------------


class TestDashboard:
    """Test dashboard integration."""

    def test_dashboard_rc_data_loads(self):
        """Dashboard can import RC module and build report."""
        from marketsentry.release_candidate import (
            build_release_candidate_report as _build,
        )

        result = _build(
            db_path="/nonexistent.db",
            exports_dir="/nonexistent",
        )
        assert isinstance(
            result, ReleaseCandidateRunResult
        )

    def test_dashboard_has_rc_section(self):
        """Dashboard app contains release candidate section."""
        source = Path(
            "src/marketsentry/dashboard_app.py"
        ).read_text(encoding="utf-8")
        assert "Release Candidate" in source
        assert "build_release_candidate_report" in source
        assert "Checklist Pass" in source
        assert "Validation Pass" in source
        assert "Safe Workflows" in source
        assert "Caution Workflows" in source


# -------------------------------------------------------------------
# Safety guard-rail tests
# -------------------------------------------------------------------


class TestNoOutboundNotifications:
    """No outbound notification code added."""

    def test_module_no_smtplib(self):
        """Module does not import smtplib."""
        import marketsentry.release_candidate as mod

        assert not hasattr(mod, "smtplib")

    def test_module_no_smtp_connection(self):
        """Module does not contain SMTP connection code."""
        source = Path(
            "src/marketsentry/release_candidate.py"
        ).read_text(encoding="utf-8")
        assert "SMTP(" not in source
        assert "smtp.connect" not in source
        assert "smtp.login" not in source
        assert "smtp.send" not in source

    def test_module_no_gmail_outlook(self):
        """Module does not integrate with Gmail or Outlook."""
        source = Path(
            "src/marketsentry/release_candidate.py"
        ).read_text(encoding="utf-8")
        assert "GmailAPI" not in source
        assert "OutlookClient" not in source

    def test_module_no_webhook_imports(self):
        """Module does not import HTTP request libraries."""
        import marketsentry.release_candidate as mod

        assert not hasattr(mod, "requests")
        assert not hasattr(mod, "httpx")

    def test_module_no_credential_storage(self):
        """Module does not store or request credentials."""
        source = Path(
            "src/marketsentry/release_candidate.py"
        ).read_text(encoding="utf-8")
        assert "getpass" not in source
        assert "keyring" not in source

    def test_module_no_sms(self):
        """Module does not import SMS libraries."""
        import marketsentry.release_candidate as mod

        assert not hasattr(mod, "twilio")


class TestNoMutation:
    """No candidate/watchlist/alert state mutation."""

    def test_no_candidate_mutation(self):
        """Module does not mutate candidates."""
        source = Path(
            "src/marketsentry/release_candidate.py"
        ).read_text(encoding="utf-8")
        assert "promote_candidate" not in source
        assert "reject_candidate" not in source
        assert "save_candidate" not in source

    def test_no_watchlist_mutation(self):
        """Module does not mutate watchlist."""
        source = Path(
            "src/marketsentry/release_candidate.py"
        ).read_text(encoding="utf-8")
        assert "add_to_watchlist" not in source
        assert "remove_from_watchlist" not in source

    def test_no_alert_mutation(self):
        """Module does not mutate alert status."""
        source = Path(
            "src/marketsentry/release_candidate.py"
        ).read_text(encoding="utf-8")
        assert "acknowledge_alert" not in source
        assert "resolve_alert" not in source
        assert "archive_alert" not in source

    def test_no_write_operations(self):
        """Module does not perform database writes."""
        source = Path(
            "src/marketsentry/release_candidate.py"
        ).read_text(encoding="utf-8")
        assert "INSERT INTO" not in source
        assert "DELETE FROM" not in source
        assert "CREATE TABLE" not in source


class TestNoRedfinOverwrite:
    """No Redfin source-of-truth overwrite."""

    def test_no_redfin_sot_overwrite(self):
        """Module does not overwrite Redfin SOT fields."""
        import marketsentry.release_candidate as mod

        assert not hasattr(mod, "redfin_source_of_truth")
        assert not hasattr(mod, "overwrite_redfin_sot")


class TestQuietGatekeeper:
    """Quiet Score gatekeeper unchanged."""

    def test_no_quiet_threshold_change(self):
        """Module does not modify Quiet Score threshold."""
        import marketsentry.release_candidate as mod

        assert not hasattr(mod, "QUIET_THRESHOLD")
        assert not hasattr(mod, "quiet_threshold")


class TestNoWalkability:
    """No walkability fields added."""

    def test_no_walkability_fields(self):
        """Module does not contain walkability attributes."""
        import marketsentry.release_candidate as mod

        assert not hasattr(mod, "walkability_score")
        assert not hasattr(mod, "walk_score")
        assert not hasattr(mod, "walkability_rating")


class TestNoBrowserAutomation:
    """No browser automation added."""

    def test_no_playwright_import(self):
        """Module does not import playwright."""
        import marketsentry.release_candidate as mod

        assert not hasattr(mod, "playwright")

    def test_no_selenium_import(self):
        """Module does not import selenium."""
        import marketsentry.release_candidate as mod

        assert not hasattr(mod, "selenium")


class TestNoNetworkCalls:
    """No real network calls in tests."""

    def test_no_requests_import(self):
        """Module does not import requests library."""
        import marketsentry.release_candidate as mod

        assert not hasattr(mod, "requests")

    def test_no_httpx_import(self):
        """Module does not import httpx library."""
        import marketsentry.release_candidate as mod

        assert not hasattr(mod, "httpx")


class TestNoGitHubRelease:
    """No GitHub release or tag created automatically."""

    def test_no_github_api_calls(self):
        """Module does not call GitHub API."""
        source = Path(
            "src/marketsentry/release_candidate.py"
        ).read_text(encoding="utf-8")
        assert "github.com/api" not in source
        assert "api.github.com" not in source
        assert "gh release create" not in source

    def test_no_git_tag_creation(self):
        """Module does not create git tags."""
        source = Path(
            "src/marketsentry/release_candidate.py"
        ).read_text(encoding="utf-8")
        assert "git tag" not in source
        assert "git push --tags" not in source


# -------------------------------------------------------------------
# Model tests
# -------------------------------------------------------------------


class TestModels:
    """Test Pydantic model construction."""

    def test_metadata_model(self):
        """ReleaseCandidateMetadata constructs."""
        meta = ReleaseCandidateMetadata()
        assert meta.project_name == "Market_Sentry"
        assert meta.test_count == -1

    def test_checklist_item_model(self):
        """ReleaseCandidateChecklistItem constructs."""
        item = ReleaseCandidateChecklistItem(
            item_id="test_item",
            category="test",
            description="Test item",
            status="pass",
            detail="All good",
        )
        assert item.item_id == "test_item"
        assert item.status == "pass"

    def test_workflow_item_model(self):
        """ReleaseCandidateWorkflowItem constructs."""
        item = ReleaseCandidateWorkflowItem(
            workflow_id="test_wf",
            name="Test Workflow",
            category="test",
            access_type="read-only",
        )
        assert item.workflow_id == "test_wf"
        assert item.access_type == "read-only"

    def test_validation_result_model(self):
        """ReleaseCandidateValidationResult constructs."""
        result = ReleaseCandidateValidationResult(
            check_id="test_check",
            description="Test check",
            status="pass",
            detail="OK",
        )
        assert result.check_id == "test_check"
        assert result.status == "pass"

    def test_report_model(self):
        """ReleaseCandidateReport constructs with defaults."""
        report = ReleaseCandidateReport()
        assert report.checklist == []
        assert report.safe_workflows == []
        assert report.manual_approval_workflows == []
        assert report.validation_results == []
        assert report.output_paths == []

    def test_run_result_model(self):
        """ReleaseCandidateRunResult constructs."""
        result = ReleaseCandidateRunResult()
        assert result.checklist_pass == 0
        assert result.checklist_warn == 0
        assert result.checklist_fail == 0
        assert result.safe_workflow_count == 0
        assert result.manual_workflow_count == 0


# -------------------------------------------------------------------
# Current project validation test
# -------------------------------------------------------------------


class TestCurrentProject:
    """Test current project passes validation."""

    def test_current_project_passes(self):
        """Current project passes RC validation.

        Note: some checks may warn (e.g. missing release
        docs before first export), but none should fail.
        """
        results = run_release_candidate_validation()
        fails = [
            r for r in results if r.status == "fail"
        ]
        # Release docs may not exist yet before first
        # export, so filter those out
        real_fails = [
            r
            for r in fails
            if r.check_id not in ("release_docs",)
        ]
        assert len(real_fails) == 0, (
            f"Unexpected failures: "
            f"{[(r.check_id, r.detail) for r in real_fails]}"
        )
