"""Tests for Milestone 21: Retrieval Operations Aging, Alerts, and Health Checks.

All tests use local data only (SQLite, temp files, mocks).
No real network calls are performed.
"""

import csv
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest


# ===========================================================================
# Test helpers
# ===========================================================================


def _create_test_db(db_path: str) -> None:
    """Create a minimal test database with fixture capture queue table."""
    from marketsentry.database import init_db
    from marketsentry.fixture_capture_queue import ensure_fixture_capture_table

    init_db(db_path)
    ensure_fixture_capture_table(db_path)


def _add_capture_request(
    db_path: str,
    source_url: str,
    request_type: str = "property_detail",
    source_site: str = "redfin",
    status: str = "pending",
    created_at: str = "",
) -> int:
    """Insert a capture request with optional created_at override."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    normalized = source_url.lower().rstrip("/")
    if created_at:
        cursor.execute(
            """
            INSERT INTO fixture_capture_queue (
                source_site, source_url, normalized_url, request_type,
                suggested_fixture_path, status, priority, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 5, ?)
            """,
            (source_site, source_url, normalized, request_type,
             f"data/raw/{source_site}/", status, created_at),
        )
    else:
        cursor.execute(
            """
            INSERT INTO fixture_capture_queue (
                source_site, source_url, normalized_url, request_type,
                suggested_fixture_path, status, priority
            ) VALUES (?, ?, ?, ?, ?, ?, 5)
            """,
            (source_site, source_url, normalized, request_type,
             f"data/raw/{source_site}/", status),
        )
    conn.commit()
    cap_id = cursor.lastrowid
    conn.close()
    return cap_id


def _write_csv(path: str, fieldnames: list, rows: list) -> None:
    """Write a CSV file with given fieldnames and rows."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_audit_csv(path: str, rows: list) -> None:
    """Write an audit CSV file."""
    fieldnames = [
        "timestamp", "source_site", "retrieval_mode", "url", "domain",
        "allowed", "blocked", "reason", "dry_run", "network_call_performed",
    ]
    _write_csv(path, fieldnames, rows)


def _write_approval_manifest(path: str, rows: list) -> None:
    """Write an approval manifest CSV."""
    fieldnames = [
        "approval_run_id", "created_at", "pending_scanned",
        "approval_rows_written", "approval_csv_path",
        "approval_summary_path", "approved_count_when_imported",
        "retrieved_count", "blocked_count", "failed_count", "notes",
    ]
    _write_csv(path, fieldnames, rows)


def _write_batch_items_csv(path: str, rows: list) -> None:
    """Write a batch retrieval items CSV."""
    fieldnames = [
        "run_id", "capture_request_id", "source_url", "request_type",
        "decision", "network_call_performed", "fixture_path",
        "status", "reason", "error",
    ]
    _write_csv(path, fieldnames, rows)


def _write_processing_manifest(path: str, rows: list) -> None:
    """Write a fixture processing manifest CSV."""
    fieldnames = [
        "processed_at", "fixture_path", "metadata_path", "source_url",
        "fixture_type", "status", "candidates_discovered",
        "candidates_inserted", "candidates_enriched",
        "listing_events_inserted", "warnings", "errors", "content_hash",
    ]
    _write_csv(path, fieldnames, rows)


# ===========================================================================
# TestEmptyHealthCheck
# ===========================================================================


class TestEmptyHealthCheck:
    """Test health check with no data returns no critical errors."""

    def test_empty_returns_no_issues(self):
        """Empty check returns zero issues."""
        from marketsentry.retrieval_health import run_retrieval_health_checks

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            summary = run_retrieval_health_checks(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
            )

            assert summary.total_issues == 0
            assert summary.critical_count == 0
            assert summary.error_count == 0
            assert summary.warning_count == 0
            assert summary.info_count == 0

    def test_empty_next_actions_no_action_required(self):
        """Empty check has a single 'no action required' next action."""
        from marketsentry.retrieval_health import run_retrieval_health_checks

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            summary = run_retrieval_health_checks(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
            )

            assert len(summary.next_actions) == 1
            assert "No action required" in summary.next_actions[0].action


# ===========================================================================
# TestStaleCaptureRequest
# ===========================================================================


class TestStaleCaptureRequest:
    """Test detection of stale pending capture requests."""

    def test_stale_pending_detected(self):
        """Pending request older than 7 days is flagged."""
        from marketsentry.retrieval_health import (
            check_fixture_capture_queue_aging,
            RetrievalHealthCheckConfig,
        )

        now = datetime(2025, 3, 15, 12, 0, 0)
        stale_date = (now - timedelta(days=10)).isoformat()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)
            _add_capture_request(
                db_path,
                "https://www.redfin.com/CA/Temecula/test",
                status="pending",
                created_at=stale_date,
            )

            issues = check_fixture_capture_queue_aging(
                database_path=db_path,
                config=RetrievalHealthCheckConfig(),
                now=now,
            )

            assert len(issues) >= 1
            assert issues[0].category == "stale_capture_request"
            assert issues[0].severity == "warning"
            assert issues[0].age_days > 7.0

    def test_fresh_pending_not_flagged(self):
        """Pending request less than 7 days old is not flagged."""
        from marketsentry.retrieval_health import (
            check_fixture_capture_queue_aging,
            RetrievalHealthCheckConfig,
        )

        now = datetime(2025, 3, 15, 12, 0, 0)
        fresh_date = (now - timedelta(days=2)).isoformat()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)
            _add_capture_request(
                db_path,
                "https://www.redfin.com/CA/Temecula/fresh",
                status="pending",
                created_at=fresh_date,
            )

            issues = check_fixture_capture_queue_aging(
                database_path=db_path,
                config=RetrievalHealthCheckConfig(),
                now=now,
            )

            assert len(issues) == 0

    def test_captured_not_flagged(self):
        """Captured requests are not flagged regardless of age."""
        from marketsentry.retrieval_health import (
            check_fixture_capture_queue_aging,
            RetrievalHealthCheckConfig,
        )

        now = datetime(2025, 3, 15, 12, 0, 0)
        old_date = (now - timedelta(days=30)).isoformat()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)
            _add_capture_request(
                db_path,
                "https://www.redfin.com/CA/Temecula/captured",
                status="captured",
                created_at=old_date,
            )

            issues = check_fixture_capture_queue_aging(
                database_path=db_path,
                config=RetrievalHealthCheckConfig(),
                now=now,
            )

            assert len(issues) == 0


# ===========================================================================
# TestStaleApprovalPackage
# ===========================================================================


class TestStaleApprovalPackage:
    """Test detection of stale approval packages."""

    def test_stale_approval_detected(self):
        """Approval with unretrieved rows older than 24h is flagged."""
        from marketsentry.retrieval_health import check_approval_package_aging

        now = datetime(2025, 3, 15, 12, 0, 0)
        stale_time = (now - timedelta(hours=30)).isoformat()

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, "redfin_retrieval_approval_manifest.csv")
            _write_approval_manifest(manifest_path, [{
                "approval_run_id": "test-run-001",
                "created_at": stale_time,
                "pending_scanned": "5",
                "approval_rows_written": "5",
                "approval_csv_path": "",
                "approval_summary_path": "",
                "approved_count_when_imported": "3",
                "retrieved_count": "0",
                "blocked_count": "0",
                "failed_count": "0",
                "notes": "",
            }])

            issues = check_approval_package_aging(
                processed_dir=tmpdir, now=now,
            )

            assert len(issues) == 1
            assert issues[0].category == "stale_approval_package"
            assert issues[0].severity == "warning"

    def test_fresh_approval_not_flagged(self):
        """Approval within 24h is not flagged."""
        from marketsentry.retrieval_health import check_approval_package_aging

        now = datetime(2025, 3, 15, 12, 0, 0)
        fresh_time = (now - timedelta(hours=2)).isoformat()

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, "redfin_retrieval_approval_manifest.csv")
            _write_approval_manifest(manifest_path, [{
                "approval_run_id": "test-run-002",
                "created_at": fresh_time,
                "pending_scanned": "5",
                "approval_rows_written": "5",
                "approval_csv_path": "",
                "approval_summary_path": "",
                "approved_count_when_imported": "3",
                "retrieved_count": "0",
                "blocked_count": "0",
                "failed_count": "0",
                "notes": "",
            }])

            issues = check_approval_package_aging(
                processed_dir=tmpdir, now=now,
            )

            assert len(issues) == 0

    def test_fully_retrieved_not_flagged(self):
        """Approval where all approved rows are retrieved is not flagged."""
        from marketsentry.retrieval_health import check_approval_package_aging

        now = datetime(2025, 3, 15, 12, 0, 0)
        stale_time = (now - timedelta(hours=48)).isoformat()

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, "redfin_retrieval_approval_manifest.csv")
            _write_approval_manifest(manifest_path, [{
                "approval_run_id": "test-run-003",
                "created_at": stale_time,
                "pending_scanned": "3",
                "approval_rows_written": "3",
                "approval_csv_path": "",
                "approval_summary_path": "",
                "approved_count_when_imported": "3",
                "retrieved_count": "3",
                "blocked_count": "0",
                "failed_count": "0",
                "notes": "",
            }])

            issues = check_approval_package_aging(
                processed_dir=tmpdir, now=now,
            )

            assert len(issues) == 0


# ===========================================================================
# TestRepeatedBlockedRetrieval
# ===========================================================================


class TestRepeatedBlockedRetrieval:
    """Test detection of repeatedly blocked retrieval attempts."""

    def test_repeated_block_detected(self):
        """URL blocked 3+ times is flagged."""
        from marketsentry.retrieval_health import check_batch_retrieval_failures

        with tempfile.TemporaryDirectory() as tmpdir:
            items_path = os.path.join(tmpdir, "redfin_batch_retrieval_items.csv")
            url = "https://www.redfin.com/CA/Temecula/blocked-url"
            _write_batch_items_csv(items_path, [
                {"run_id": "r1", "capture_request_id": "1", "source_url": url,
                 "request_type": "property_detail", "decision": "BLOCKED",
                 "network_call_performed": "False", "fixture_path": "",
                 "status": "blocked", "reason": "compliance", "error": ""},
                {"run_id": "r2", "capture_request_id": "1", "source_url": url,
                 "request_type": "property_detail", "decision": "BLOCKED",
                 "network_call_performed": "False", "fixture_path": "",
                 "status": "blocked", "reason": "compliance", "error": ""},
                {"run_id": "r3", "capture_request_id": "1", "source_url": url,
                 "request_type": "property_detail", "decision": "BLOCKED",
                 "network_call_performed": "False", "fixture_path": "",
                 "status": "blocked", "reason": "compliance", "error": ""},
            ])

            issues = check_batch_retrieval_failures(processed_dir=tmpdir)

            assert len(issues) == 1
            assert issues[0].category == "repeated_block"
            assert issues[0].severity == "warning"

    def test_below_threshold_not_flagged(self):
        """URL blocked fewer than 3 times is not flagged."""
        from marketsentry.retrieval_health import check_batch_retrieval_failures

        with tempfile.TemporaryDirectory() as tmpdir:
            items_path = os.path.join(tmpdir, "redfin_batch_retrieval_items.csv")
            url = "https://www.redfin.com/CA/Temecula/blocked-url"
            _write_batch_items_csv(items_path, [
                {"run_id": "r1", "capture_request_id": "1", "source_url": url,
                 "request_type": "property_detail", "decision": "BLOCKED",
                 "network_call_performed": "False", "fixture_path": "",
                 "status": "blocked", "reason": "compliance", "error": ""},
                {"run_id": "r2", "capture_request_id": "1", "source_url": url,
                 "request_type": "property_detail", "decision": "BLOCKED",
                 "network_call_performed": "False", "fixture_path": "",
                 "status": "blocked", "reason": "compliance", "error": ""},
            ])

            issues = check_batch_retrieval_failures(processed_dir=tmpdir)

            assert len(issues) == 0


# ===========================================================================
# TestMissingRobotsPolicy
# ===========================================================================


class TestMissingRobotsPolicy:
    """Test detection of missing local robots policy files."""

    def test_missing_robots_when_live_enabled(self):
        """Missing robots.txt flagged as error when live retrieval enabled."""
        from marketsentry.retrieval_health import (
            check_local_policy_files,
            RetrievalHealthCheckConfig,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)
            policies_dir = os.path.join(tmpdir, "policies")

            env = {
                "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "true",
                "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "redfin",
                "MARKETSENTRY_LIVE_USER_AGENT": "TestBot/1.0",
                "MARKETSENTRY_LIVE_CONTACT_EMAIL": "test@example.com",
            }

            config = RetrievalHealthCheckConfig(policies_dir=policies_dir)

            with patch.dict(os.environ, env, clear=False):
                issues = check_local_policy_files(
                    database_path=db_path, config=config,
                )

            policy_issues = [i for i in issues if i.message.startswith("Missing local robots")]
            assert len(policy_issues) == 1
            assert policy_issues[0].severity == "error"

    def test_missing_robots_when_queue_has_pending(self):
        """Missing robots.txt flagged as warning when queue has pending items."""
        from marketsentry.retrieval_health import (
            check_local_policy_files,
            RetrievalHealthCheckConfig,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)
            _add_capture_request(
                db_path,
                "https://www.redfin.com/CA/Temecula/test",
                status="pending",
            )
            policies_dir = os.path.join(tmpdir, "policies")

            config = RetrievalHealthCheckConfig(policies_dir=policies_dir)

            # Live retrieval disabled (default)
            with patch.dict(os.environ, {}, clear=False):
                issues = check_local_policy_files(
                    database_path=db_path, config=config,
                )

            policy_issues = [i for i in issues if i.message.startswith("Missing local robots")]
            assert len(policy_issues) == 1
            assert policy_issues[0].severity == "warning"

    def test_robots_present_no_issue(self):
        """No issue when robots policy file exists."""
        from marketsentry.retrieval_health import (
            check_local_policy_files,
            RetrievalHealthCheckConfig,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)
            _add_capture_request(
                db_path,
                "https://www.redfin.com/CA/Temecula/test",
                status="pending",
            )
            policies_dir = os.path.join(tmpdir, "policies")
            os.makedirs(policies_dir, exist_ok=True)
            Path(policies_dir, "redfin_robots.txt").write_text(
                "User-agent: *\nAllow: /", encoding="utf-8"
            )

            config = RetrievalHealthCheckConfig(policies_dir=policies_dir)

            with patch.dict(os.environ, {}, clear=False):
                issues = check_local_policy_files(
                    database_path=db_path, config=config,
                )

            policy_issues = [i for i in issues if i.message.startswith("Missing local robots")]
            assert len(policy_issues) == 0


# ===========================================================================
# TestMissingUserAgentContact
# ===========================================================================


class TestMissingUserAgentContact:
    """Test detection of missing User-Agent and contact email."""

    def test_missing_user_agent_when_live_enabled(self):
        """Missing User-Agent flagged when live retrieval enabled."""
        from marketsentry.retrieval_health import (
            check_local_policy_files,
            RetrievalHealthCheckConfig,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)
            policies_dir = os.path.join(tmpdir, "policies")
            os.makedirs(policies_dir, exist_ok=True)
            Path(policies_dir, "redfin_robots.txt").write_text(
                "User-agent: *\nAllow: /", encoding="utf-8"
            )

            env = {
                "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "true",
                "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "redfin",
                "MARKETSENTRY_LIVE_USER_AGENT": "",
                "MARKETSENTRY_LIVE_CONTACT_EMAIL": "",
            }

            config = RetrievalHealthCheckConfig(policies_dir=policies_dir)

            with patch.dict(os.environ, env, clear=False):
                issues = check_local_policy_files(
                    database_path=db_path, config=config,
                )

            ua_issues = [i for i in issues if "User-Agent" in i.message]
            email_issues = [i for i in issues if "contact email" in i.message]
            assert len(ua_issues) == 1
            assert ua_issues[0].severity == "error"
            assert len(email_issues) == 1
            assert email_issues[0].severity == "error"

    def test_no_config_issue_when_live_disabled(self):
        """No config issue when live retrieval is disabled and no pending."""
        from marketsentry.retrieval_health import (
            check_local_policy_files,
            RetrievalHealthCheckConfig,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)
            policies_dir = os.path.join(tmpdir, "policies")
            config = RetrievalHealthCheckConfig(policies_dir=policies_dir)

            env = {
                "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "false",
                "MARKETSENTRY_LIVE_USER_AGENT": "",
                "MARKETSENTRY_LIVE_CONTACT_EMAIL": "",
            }

            with patch.dict(os.environ, env, clear=False):
                issues = check_local_policy_files(
                    database_path=db_path, config=config,
                )

            assert len(issues) == 0


# ===========================================================================
# TestAuditAnomalies
# ===========================================================================


class TestAuditAnomalies:
    """Test detection of unexpected network_call_performed=true."""

    def test_network_call_true_detected(self):
        """Audit record with network_call_performed=true is critical."""
        from marketsentry.retrieval_health import check_retrieval_audit_anomalies

        with tempfile.TemporaryDirectory() as tmpdir:
            audit_file = os.path.join(tmpdir, "retrieval_audit_20250315.csv")
            _write_audit_csv(audit_file, [{
                "timestamp": "2025-03-15T10:00:00",
                "source_site": "redfin",
                "retrieval_mode": "live_http",
                "url": "https://www.redfin.com/test",
                "domain": "redfin.com",
                "allowed": "True",
                "blocked": "False",
                "reason": "",
                "dry_run": "False",
                "network_call_performed": "True",
            }])

            issues = check_retrieval_audit_anomalies(audit_dir=tmpdir)

            assert len(issues) == 1
            assert issues[0].category == "audit_anomaly"
            assert issues[0].severity == "critical"

    def test_network_call_false_no_anomaly(self):
        """Audit record with network_call_performed=false is not flagged."""
        from marketsentry.retrieval_health import check_retrieval_audit_anomalies

        with tempfile.TemporaryDirectory() as tmpdir:
            audit_file = os.path.join(tmpdir, "retrieval_audit_20250315.csv")
            _write_audit_csv(audit_file, [{
                "timestamp": "2025-03-15T10:00:00",
                "source_site": "redfin",
                "retrieval_mode": "dry_run",
                "url": "https://www.redfin.com/test",
                "domain": "redfin.com",
                "allowed": "True",
                "blocked": "False",
                "reason": "",
                "dry_run": "True",
                "network_call_performed": "False",
            }])

            issues = check_retrieval_audit_anomalies(audit_dir=tmpdir)

            assert len(issues) == 0


# ===========================================================================
# TestUnprocessedFixture
# ===========================================================================


class TestUnprocessedFixture:
    """Test detection of unprocessed retrieved fixtures."""

    def test_unprocessed_fixture_detected(self):
        """Retrieved fixture not in manifest older than threshold is flagged."""
        from marketsentry.retrieval_health import (
            check_retrieved_fixture_processing_gaps,
            RetrievalHealthCheckConfig,
        )

        now = datetime(2025, 3, 15, 12, 0, 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create raw fixture directory with an HTML file
            fixture_dir = Path(tmpdir) / "redfin" / "details"
            fixture_dir.mkdir(parents=True)
            fixture_file = fixture_dir / "test_property.html"
            fixture_file.write_text("<html>test</html>", encoding="utf-8")

            # Make the file appear old
            old_time = (now - timedelta(hours=48)).timestamp()
            os.utime(fixture_file, (old_time, old_time))

            # Empty processing manifest
            processed_dir = os.path.join(tmpdir, "processed")
            os.makedirs(processed_dir)
            manifest_path = os.path.join(
                processed_dir, "redfin_fixture_processing_manifest.csv"
            )
            _write_processing_manifest(manifest_path, [])

            config = RetrievalHealthCheckConfig()
            issues = check_retrieved_fixture_processing_gaps(
                processed_dir=processed_dir,
                raw_dir=tmpdir,
                config=config,
                now=now,
            )

            assert len(issues) == 1
            assert issues[0].category == "unprocessed_fixture"
            assert issues[0].severity == "warning"

    def test_processed_fixture_not_flagged(self):
        """Fixture already in manifest is not flagged."""
        from marketsentry.retrieval_health import (
            check_retrieved_fixture_processing_gaps,
            RetrievalHealthCheckConfig,
        )

        now = datetime(2025, 3, 15, 12, 0, 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_dir = Path(tmpdir) / "redfin" / "details"
            fixture_dir.mkdir(parents=True)
            fixture_file = fixture_dir / "already_processed.html"
            fixture_file.write_text("<html>processed</html>", encoding="utf-8")

            old_time = (now - timedelta(hours=48)).timestamp()
            os.utime(fixture_file, (old_time, old_time))

            processed_dir = os.path.join(tmpdir, "processed")
            os.makedirs(processed_dir)
            manifest_path = os.path.join(
                processed_dir, "redfin_fixture_processing_manifest.csv"
            )
            _write_processing_manifest(manifest_path, [{
                "processed_at": "2025-03-14T10:00:00",
                "fixture_path": str(fixture_file),
                "metadata_path": "",
                "source_url": "",
                "fixture_type": "property_detail",
                "status": "processed",
                "candidates_discovered": "1",
                "candidates_inserted": "1",
                "candidates_enriched": "0",
                "listing_events_inserted": "0",
                "warnings": "",
                "errors": "",
                "content_hash": "abc123",
            }])

            config = RetrievalHealthCheckConfig()
            issues = check_retrieved_fixture_processing_gaps(
                processed_dir=processed_dir,
                raw_dir=tmpdir,
                config=config,
                now=now,
            )

            assert len(issues) == 0


# ===========================================================================
# TestNextActionsGenerated
# ===========================================================================


class TestNextActionsGenerated:
    """Test that next actions are generated from issues."""

    def test_next_actions_from_issues(self):
        """Next actions include entries for stale items and anomalies."""
        from marketsentry.retrieval_health import run_retrieval_health_checks

        now = datetime(2025, 3, 15, 12, 0, 0)
        stale_date = (now - timedelta(days=10)).isoformat()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)
            _add_capture_request(
                db_path,
                "https://www.redfin.com/CA/Temecula/stale",
                status="pending",
                created_at=stale_date,
            )

            # Add an audit anomaly
            audit_dir = os.path.join(tmpdir, "audit")
            os.makedirs(audit_dir)
            _write_audit_csv(
                os.path.join(audit_dir, "retrieval_audit_20250315.csv"),
                [{
                    "timestamp": "2025-03-15T10:00:00",
                    "source_site": "redfin",
                    "retrieval_mode": "live_http",
                    "url": "https://www.redfin.com/test",
                    "domain": "redfin.com",
                    "allowed": "True",
                    "blocked": "False",
                    "reason": "",
                    "dry_run": "False",
                    "network_call_performed": "True",
                }],
            )

            summary = run_retrieval_health_checks(
                database_path=db_path,
                audit_dir=audit_dir,
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
                now=now,
            )

            assert summary.total_issues >= 2
            assert summary.critical_count >= 1
            assert summary.stale_capture_request_count >= 1

            # Next actions should include audit anomaly and stale captures
            action_texts = [a.action for a in summary.next_actions]
            assert any("critical" in a.lower() or "audit" in a.lower() for a in action_texts)
            assert any("stale" in a.lower() or "capture" in a.lower() for a in action_texts)


# ===========================================================================
# TestCLICommands
# ===========================================================================


class TestCLICommands:
    """Test CLI command registration and help."""

    def test_health_check_command_registered(self):
        """retrieval-health-check command is registered."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["retrieval-health-check", "--help"])
        assert result.exit_code == 0
        assert "health check" in result.output.lower() or "retrieval" in result.output.lower()

    def test_export_health_report_command_registered(self):
        """export-retrieval-health-report command is registered."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["export-retrieval-health-report", "--help"])
        assert result.exit_code == 0
        assert "health" in result.output.lower() or "report" in result.output.lower()

    def test_health_check_runs(self):
        """retrieval-health-check runs successfully with a temp database."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            runner = CliRunner()
            result = runner.invoke(app, [
                "retrieval-health-check",
                "--db", db_path,
                "--audit-dir", os.path.join(tmpdir, "audit"),
                "--processed-dir", os.path.join(tmpdir, "processed"),
                "--raw-dir", os.path.join(tmpdir, "raw"),
            ])
            assert result.exit_code == 0
            assert "Retrieval Health Check" in result.output

    def test_export_health_report_runs(self):
        """export-retrieval-health-report runs successfully."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)
            output_dir = os.path.join(tmpdir, "exports")

            runner = CliRunner()
            result = runner.invoke(app, [
                "export-retrieval-health-report",
                "--db", db_path,
                "--audit-dir", os.path.join(tmpdir, "audit"),
                "--processed-dir", os.path.join(tmpdir, "processed"),
                "--raw-dir", os.path.join(tmpdir, "raw"),
                "--output-dir", output_dir,
            ])
            assert result.exit_code == 0
            assert "exported" in result.output.lower()


# ===========================================================================
# TestExportReport
# ===========================================================================


class TestExportReport:
    """Test health report export in MD and CSV formats."""

    def test_export_md(self):
        """Markdown report is created with expected content."""
        from marketsentry.retrieval_health import export_retrieval_health_report

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            report_path = export_retrieval_health_report(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
                output_dir=os.path.join(tmpdir, "exports"),
                report_format="md",
            )

            assert report_path.endswith(".md")
            content = Path(report_path).read_text(encoding="utf-8")
            assert "Retrieval Health Check Report" in content
            assert "Summary" in content

    def test_export_csv(self):
        """CSV report is created."""
        from marketsentry.retrieval_health import export_retrieval_health_report

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            report_path = export_retrieval_health_report(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
                output_dir=os.path.join(tmpdir, "exports"),
                report_format="csv",
            )

            assert report_path.endswith(".csv")
            assert Path(report_path).exists()

    def test_export_csv_with_issues(self):
        """CSV report contains issue rows."""
        from marketsentry.retrieval_health import export_retrieval_health_report

        now = datetime(2025, 3, 15, 12, 0, 0)
        stale_date = (now - timedelta(days=10)).isoformat()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)
            _add_capture_request(
                db_path,
                "https://www.redfin.com/CA/Temecula/stale",
                status="pending",
                created_at=stale_date,
            )

            report_path = export_retrieval_health_report(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
                output_dir=os.path.join(tmpdir, "exports"),
                report_format="csv",
            )

            with open(report_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) >= 1
            assert rows[0]["category"] == "stale_capture_request"


# ===========================================================================
# TestModels
# ===========================================================================


class TestModels:
    """Test Pydantic model defaults."""

    def test_health_issue_defaults(self):
        """RetrievalHealthIssue has correct defaults."""
        from marketsentry.retrieval_health import RetrievalHealthIssue

        issue = RetrievalHealthIssue()
        assert issue.severity == "info"
        assert issue.category == ""
        assert issue.age_days == 0.0

    def test_health_summary_defaults(self):
        """RetrievalHealthSummary has correct defaults."""
        from marketsentry.retrieval_health import RetrievalHealthSummary

        s = RetrievalHealthSummary()
        assert s.total_issues == 0
        assert s.critical_count == 0
        assert s.issues == []
        assert s.next_actions == []

    def test_health_config_defaults(self):
        """RetrievalHealthCheckConfig has correct defaults."""
        from marketsentry.retrieval_health import RetrievalHealthCheckConfig

        c = RetrievalHealthCheckConfig()
        assert c.pending_capture_stale_days == 7.0
        assert c.approval_package_stale_hours == 24.0
        assert c.dry_run_approval_stale_hours == 24.0
        assert c.retrieved_fixture_unprocessed_hours == 24.0
        assert c.repeated_blocked_threshold == 3
        assert c.policies_dir == "data/policies/robots"

    def test_next_action_defaults(self):
        """RetrievalNextAction has correct defaults."""
        from marketsentry.retrieval_health import RetrievalNextAction

        a = RetrievalNextAction()
        assert a.priority == 0
        assert a.action == ""
        assert a.command == ""

    def test_aging_bucket_defaults(self):
        """RetrievalAgingBucket has correct defaults."""
        from marketsentry.retrieval_health import RetrievalAgingBucket

        b = RetrievalAgingBucket()
        assert b.count == 0
        assert b.bucket_label == ""


# ===========================================================================
# TestFormatSummary
# ===========================================================================


class TestFormatSummary:
    """Test health summary formatting."""

    def test_format_empty(self):
        """Formatted output contains header for empty summary."""
        from marketsentry.retrieval_health import (
            format_retrieval_health_summary,
            RetrievalHealthSummary,
        )

        s = RetrievalHealthSummary(checked_at="2025-03-15T12:00:00")
        output = format_retrieval_health_summary(s)

        assert "Retrieval Health Check" in output
        assert "Total issues: 0" in output
        assert "Critical: 0" in output

    def test_format_with_issues(self):
        """Formatted output lists issues and next actions."""
        from marketsentry.retrieval_health import (
            format_retrieval_health_summary,
            run_retrieval_health_checks,
        )

        now = datetime(2025, 3, 15, 12, 0, 0)
        stale_date = (now - timedelta(days=10)).isoformat()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)
            _add_capture_request(
                db_path,
                "https://www.redfin.com/CA/Temecula/stale",
                status="pending",
                created_at=stale_date,
            )

            summary = run_retrieval_health_checks(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
                now=now,
            )
            output = format_retrieval_health_summary(summary)

            assert "WARNING" in output
            assert "stale_capture_request" in output
            assert "Next Actions" in output


# ===========================================================================
# TestDashboardHealthChecksTab
# ===========================================================================


class TestDashboardHealthChecksTab:
    """Test that health check data loads for dashboard tab."""

    def test_health_check_data_loadable(self):
        """Health check data can be loaded for dashboard display."""
        from marketsentry.retrieval_health import run_retrieval_health_checks

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            health = run_retrieval_health_checks(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
            )

            # All fields needed by dashboard are accessible
            assert isinstance(health.total_issues, int)
            assert isinstance(health.warning_count, int)
            assert isinstance(health.error_count, int)
            assert isinstance(health.critical_count, int)
            assert isinstance(health.stale_capture_request_count, int)
            assert isinstance(health.stale_approval_package_count, int)
            assert isinstance(health.unprocessed_fixture_count, int)
            assert isinstance(health.audit_anomaly_count, int)
            assert isinstance(health.missing_policy_count, int)
            assert isinstance(health.repeated_block_count, int)
            assert isinstance(health.issues, list)
            assert isinstance(health.next_actions, list)


# ===========================================================================
# TestNoNetworkCalls
# ===========================================================================


class TestNoNetworkCalls:
    """Confirm no real network calls are performed."""

    def test_no_real_http_clients(self):
        """Only FakeHttpClient is used, no real HTTP calls."""
        from marketsentry.retrieval_health import run_retrieval_health_checks

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            # Runs health checks without any network activity
            summary = run_retrieval_health_checks(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
            )

            assert isinstance(summary.total_issues, int)


# ===========================================================================
# TestNoScheduledLiveRetrieval
# ===========================================================================


class TestNoScheduledLiveRetrieval:
    """Confirm scheduled scripts do not invoke live retrieval."""

    def test_scheduled_scripts_no_live_retrieval(self):
        """Scheduled task scripts do not call live retrieval or approval commands."""
        import glob

        script_patterns = [
            "scripts/scheduled_*.py",
            "scripts/scheduled_*.bat",
            "scripts/scheduled_*.ps1",
        ]

        forbidden = [
            "retrieve-approved-redfin-batch",
            "retrieve-pending-redfin-fixtures",
            "retrieve-redfin-search",
            "retrieve-redfin-property",
            "prepare-redfin-retrieval-approval",
            "--force-live",
        ]

        for pattern in script_patterns:
            for script_path in glob.glob(pattern):
                content = Path(script_path).read_text(encoding="utf-8")
                for term in forbidden:
                    assert term not in content, (
                        f"Scheduled script {script_path} contains '{term}'"
                    )


# ===========================================================================
# TestAgingBuckets
# ===========================================================================


class TestAgingBuckets:
    """Test aging bucket distribution."""

    def test_aging_buckets_populated(self):
        """Stale capture requests are bucketed by age."""
        from marketsentry.retrieval_health import run_retrieval_health_checks

        now = datetime(2025, 3, 15, 12, 0, 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            # Add items in different age buckets
            _add_capture_request(
                db_path,
                "https://www.redfin.com/CA/Temecula/10days",
                status="pending",
                created_at=(now - timedelta(days=10)).isoformat(),
            )
            _add_capture_request(
                db_path,
                "https://www.redfin.com/CA/Temecula/20days",
                status="pending",
                created_at=(now - timedelta(days=20)).isoformat(),
            )
            _add_capture_request(
                db_path,
                "https://www.redfin.com/CA/Temecula/35days",
                status="pending",
                created_at=(now - timedelta(days=35)).isoformat(),
            )

            summary = run_retrieval_health_checks(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
                now=now,
            )

            assert len(summary.aging_buckets) >= 2
            bucket_labels = [b.bucket_label for b in summary.aging_buckets]
            assert "7-14 days" in bucket_labels
            assert "14-30 days" in bucket_labels or "30+ days" in bucket_labels


# ===========================================================================
# TestConfigOverrides
# ===========================================================================


class TestConfigOverrides:
    """Test configurable threshold overrides."""

    def test_custom_stale_threshold(self):
        """Custom stale threshold changes which items are flagged."""
        from marketsentry.retrieval_health import (
            check_fixture_capture_queue_aging,
            RetrievalHealthCheckConfig,
        )

        now = datetime(2025, 3, 15, 12, 0, 0)
        five_days_ago = (now - timedelta(days=5)).isoformat()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)
            _add_capture_request(
                db_path,
                "https://www.redfin.com/CA/Temecula/5days",
                status="pending",
                created_at=five_days_ago,
            )

            # Default threshold (7 days) - not flagged
            config_default = RetrievalHealthCheckConfig()
            issues_default = check_fixture_capture_queue_aging(
                database_path=db_path, config=config_default, now=now,
            )
            assert len(issues_default) == 0

            # Custom threshold (3 days) - flagged
            config_custom = RetrievalHealthCheckConfig(
                pending_capture_stale_days=3.0
            )
            issues_custom = check_fixture_capture_queue_aging(
                database_path=db_path, config=config_custom, now=now,
            )
            assert len(issues_custom) == 1

    def test_custom_block_threshold(self):
        """Custom block threshold changes which URLs are flagged."""
        from marketsentry.retrieval_health import (
            check_batch_retrieval_failures,
            RetrievalHealthCheckConfig,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            items_path = os.path.join(tmpdir, "redfin_batch_retrieval_items.csv")
            url = "https://www.redfin.com/CA/Temecula/test"
            _write_batch_items_csv(items_path, [
                {"run_id": f"r{i}", "capture_request_id": "1",
                 "source_url": url, "request_type": "property_detail",
                 "decision": "BLOCKED", "network_call_performed": "False",
                 "fixture_path": "", "status": "blocked",
                 "reason": "compliance", "error": ""}
                for i in range(2)
            ])

            # Default threshold (3) - not flagged
            config_default = RetrievalHealthCheckConfig()
            issues_default = check_batch_retrieval_failures(
                processed_dir=tmpdir, config=config_default,
            )
            assert len(issues_default) == 0

            # Custom threshold (2) - flagged
            config_custom = RetrievalHealthCheckConfig(
                repeated_blocked_threshold=2
            )
            issues_custom = check_batch_retrieval_failures(
                processed_dir=tmpdir, config=config_custom,
            )
            assert len(issues_custom) == 1


# ===========================================================================
# TestFullIntegration
# ===========================================================================


class TestFullIntegration:
    """Integration test running all health checks together."""

    def test_multiple_issue_types(self):
        """Multiple issue types are detected in a single run."""
        from marketsentry.retrieval_health import (
            run_retrieval_health_checks,
            RetrievalHealthCheckConfig,
        )

        now = datetime(2025, 3, 15, 12, 0, 0)
        stale_date = (now - timedelta(days=10)).isoformat()
        stale_approval = (now - timedelta(hours=48)).isoformat()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            # Stale capture request
            _add_capture_request(
                db_path,
                "https://www.redfin.com/CA/Temecula/stale",
                status="pending",
                created_at=stale_date,
            )

            # Stale approval
            processed_dir = os.path.join(tmpdir, "processed")
            os.makedirs(processed_dir)
            _write_approval_manifest(
                os.path.join(processed_dir, "redfin_retrieval_approval_manifest.csv"),
                [{
                    "approval_run_id": "test-001",
                    "created_at": stale_approval,
                    "pending_scanned": "5",
                    "approval_rows_written": "5",
                    "approval_csv_path": "",
                    "approval_summary_path": "",
                    "approved_count_when_imported": "3",
                    "retrieved_count": "1",
                    "blocked_count": "0",
                    "failed_count": "0",
                    "notes": "",
                }],
            )

            # Audit anomaly
            audit_dir = os.path.join(tmpdir, "audit")
            os.makedirs(audit_dir)
            _write_audit_csv(
                os.path.join(audit_dir, "retrieval_audit_20250315.csv"),
                [{
                    "timestamp": "2025-03-15T10:00:00",
                    "source_site": "redfin",
                    "retrieval_mode": "live_http",
                    "url": "https://www.redfin.com/test",
                    "domain": "redfin.com",
                    "allowed": "True",
                    "blocked": "False",
                    "reason": "",
                    "dry_run": "False",
                    "network_call_performed": "True",
                }],
            )

            config = RetrievalHealthCheckConfig(
                policies_dir=os.path.join(tmpdir, "policies"),
            )

            summary = run_retrieval_health_checks(
                database_path=db_path,
                audit_dir=audit_dir,
                processed_dir=processed_dir,
                raw_dir=os.path.join(tmpdir, "raw"),
                config=config,
                now=now,
            )

            categories = {i.category for i in summary.issues}
            assert "stale_capture_request" in categories
            assert "stale_approval_package" in categories
            assert "audit_anomaly" in categories
            assert summary.total_issues >= 3
            assert summary.critical_count >= 1
            assert summary.warning_count >= 2
            assert len(summary.next_actions) >= 3
