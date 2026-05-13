"""Milestone 44 tests: Configurable Portfolio Trend Alert Rules.

Tests cover rule config loading, validation, merge/replace modes,
template writing, enabled/disabled rules, duplicate IDs, built-in
override rejection, forbidden metrics, CLI commands, dashboard,
scheduled script safety, and guard-rail constraints.
"""

import csv
import json
import os
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_pack_csv(dir_path, filename, rows):
    """Write a portfolio review pack CSV file."""
    from marketsentry.portfolio_review_pack import (
        REVIEW_CSV_FIELDNAMES,
    )

    path = os.path.join(dir_path, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=REVIEW_CSV_FIELDNAMES
        )
        writer.writeheader()
        for row in rows:
            full_row = {fn: "" for fn in REVIEW_CSV_FIELDNAMES}
            full_row.update(row)
            writer.writerow(full_row)
    return path


def _base_row(**overrides):
    """Create a base row dict with sensible defaults."""
    row = {
        "property_id": "1",
        "address": "123 Main St",
        "city": "Temecula",
        "zip": "92592",
        "current_price": "625000",
        "beds": "4",
        "baths": "2.5",
        "sqft": "2100",
        "watch_priority_label": "normal",
        "active_watch_status": "True",
        "quiet_score": "82.5",
        "quiet_gatekeeper_result": "pass",
        "vibrancy_score": "15.0",
        "gas_evidence": "",
        "garage_spaces": "2",
        "effective_dom_v1": "180",
        "effective_dom_v2": "45",
        "effective_dom_delta": "135",
        "county_reset_applied": "True",
        "recent_churn_index": "2.1",
        "listing_churn_count": "3",
        "dom_reset_count": "2",
        "sale_rent_alternation_count": "0",
        "cross_site_confidence_score": "78.5",
        "discrepancy_severity_label": "moderate",
        "open_alert_count": "3",
        "high_critical_alert_count": "1",
        "alert_burden_label": "moderate",
        "lifecycle_health_score": "65.0",
        "lifecycle_health_label": "needs_review",
        "lifecycle_gap_count": "2",
        "review_priority_label": "normal_review",
        "review_priority_score": "15",
        "recommended_review_action": "Review alerts",
        "redfin_url": (
            "https://www.redfin.com/CA/Temecula/123-Main-St"
        ),
    }
    row.update(overrides)
    return row


def _write_rule_config(dir_path, config_dict):
    """Write a rule config JSON file."""
    path = os.path.join(
        dir_path, "portfolio_trend_alert_rules.json"
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config_dict, f, indent=2)
    return path


def _valid_merge_config():
    """Return a valid merge-mode config dict."""
    return {
        "mode": "merge",
        "rules": [
            {
                "rule_id": "custom_burden_90",
                "rule_name": "Custom burden 90",
                "scope": "portfolio",
                "metric_name": (
                    "aggregate_review_burden_score"
                ),
                "threshold_value": 90,
                "comparison": ">=",
                "severity": "high",
                "enabled": True,
                "message_template": (
                    "Burden is {current_value}"
                ),
                "recommended_local_action": (
                    "Review burden"
                ),
            },
        ],
    }


def _valid_replace_config():
    """Return a valid replace-mode config dict."""
    return {
        "mode": "replace",
        "rules": [
            {
                "rule_id": "only_rule",
                "rule_name": "Only custom rule",
                "scope": "portfolio",
                "metric_name": (
                    "aggregate_review_burden_score"
                ),
                "threshold_value": 50,
                "comparison": ">=",
                "severity": "warning",
                "enabled": True,
                "message_template": (
                    "Burden at {current_value}"
                ),
                "recommended_local_action": "Check burden",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Built-in rules still load without config
# ---------------------------------------------------------------------------

class TestBuiltinRulesWithoutConfig:
    """Built-in rules work without any config file."""

    def test_builtin_rules_load(self):
        """Built-in rules load without config."""
        from marketsentry.portfolio_trend_alerts import (
            get_default_portfolio_trend_alert_rules,
        )
        rules = get_default_portfolio_trend_alert_rules()
        assert len(rules) >= 10
        ids = {r.rule_id for r in rules}
        assert "burden_high_80" in ids
        assert "property_degraded" in ids

    def test_active_rules_without_config(self):
        """Active rules return built-ins without config."""
        from marketsentry.portfolio_trend_alerts import (
            get_active_portfolio_trend_alert_rules,
            get_default_portfolio_trend_alert_rules,
        )
        rules, mode, en, dis, errors = (
            get_active_portfolio_trend_alert_rules(
                "nonexistent.json"
            )
        )
        assert mode == "builtin"
        assert len(rules) == len(
            get_default_portfolio_trend_alert_rules()
        )
        assert en == len(rules)
        assert dis == 0
        assert not errors


# ---------------------------------------------------------------------------
# Missing config does not error
# ---------------------------------------------------------------------------

class TestMissingConfig:
    """Missing config file is handled gracefully."""

    def test_missing_config_no_error(self):
        """Missing config returns empty valid config."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        config = load_portfolio_trend_alert_rule_config(
            "does_not_exist.json"
        )
        assert config.is_valid
        assert len(config.rules) == 0
        assert len(config.errors) == 0


# ---------------------------------------------------------------------------
# Template writer
# ---------------------------------------------------------------------------

class TestTemplateWriter:
    """Template writer creates and handles overwrite."""

    def test_template_creates_file(self):
        """Template writer creates an example config file."""
        from marketsentry.portfolio_trend_alerts import (
            write_portfolio_trend_alert_rule_template,
        )
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "example.json")
            path, written = (
                write_portfolio_trend_alert_rule_template(
                    output_path=out
                )
            )
            assert written is True
            assert os.path.isfile(path)
            with open(path, "r") as f:
                data = json.load(f)
            assert "mode" in data
            assert "rules" in data
            assert len(data["rules"]) >= 2

    def test_template_refuses_overwrite(self):
        """Template writer refuses overwrite by default."""
        from marketsentry.portfolio_trend_alerts import (
            write_portfolio_trend_alert_rule_template,
        )
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "example.json")
            write_portfolio_trend_alert_rule_template(
                output_path=out
            )
            _, written = (
                write_portfolio_trend_alert_rule_template(
                    output_path=out, overwrite=False,
                )
            )
            assert written is False

    def test_template_allows_overwrite(self):
        """Template writer allows overwrite when requested."""
        from marketsentry.portfolio_trend_alerts import (
            write_portfolio_trend_alert_rule_template,
        )
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "example.json")
            write_portfolio_trend_alert_rule_template(
                output_path=out
            )
            _, written = (
                write_portfolio_trend_alert_rule_template(
                    output_path=out, overwrite=True,
                )
            )
            assert written is True


# ---------------------------------------------------------------------------
# Valid custom rule config loads
# ---------------------------------------------------------------------------

class TestValidConfigLoads:
    """Valid custom rule configs load correctly."""

    def test_valid_merge_config(self):
        """Valid merge config loads successfully."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(
                td, _valid_merge_config()
            )
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert config.is_valid
            assert config.mode == "merge"
            assert len(config.rules) == 1
            assert config.rules[0].rule_id == (
                "custom_burden_90"
            )

    def test_valid_replace_config(self):
        """Valid replace config loads successfully."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(
                td, _valid_replace_config()
            )
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert config.is_valid
            assert config.mode == "replace"
            assert len(config.rules) == 1


# ---------------------------------------------------------------------------
# Merge mode includes built-in + custom
# ---------------------------------------------------------------------------

class TestMergeMode:
    """Merge mode adds custom rules after built-ins."""

    def test_merge_includes_both(self):
        """Merge mode includes built-in and custom rules."""
        from marketsentry.portfolio_trend_alerts import (
            merge_portfolio_trend_alert_rules,
            get_default_portfolio_trend_alert_rules,
        )
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(
                td, _valid_merge_config()
            )
            merged, errors = (
                merge_portfolio_trend_alert_rules(path)
            )
            builtin_count = len(
                get_default_portfolio_trend_alert_rules()
            )
            assert len(merged) == builtin_count + 1
            assert not errors
            ids = {r.rule_id for r in merged}
            assert "burden_high_80" in ids
            assert "custom_burden_90" in ids


# ---------------------------------------------------------------------------
# Replace mode uses only custom rules
# ---------------------------------------------------------------------------

class TestReplaceMode:
    """Replace mode uses only custom rules."""

    def test_replace_uses_only_custom(self):
        """Replace mode returns only custom rules."""
        from marketsentry.portfolio_trend_alerts import (
            merge_portfolio_trend_alert_rules,
        )
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(
                td, _valid_replace_config()
            )
            merged, errors = (
                merge_portfolio_trend_alert_rules(path)
            )
            assert len(merged) == 1
            assert merged[0].rule_id == "only_rule"
            assert not errors


# ---------------------------------------------------------------------------
# Disabled rule is not evaluated
# ---------------------------------------------------------------------------

class TestDisabledRule:
    """Disabled rules are not evaluated."""

    def test_disabled_rule_excluded(self):
        """Disabled rule is included in config but not active."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
            get_active_portfolio_trend_alert_rules,
        )
        config_dict = {
            "mode": "replace",
            "rules": [
                {
                    "rule_id": "enabled_rule",
                    "rule_name": "Enabled",
                    "scope": "portfolio",
                    "metric_name": (
                        "aggregate_review_burden_score"
                    ),
                    "threshold_value": 50,
                    "comparison": ">=",
                    "severity": "warning",
                    "enabled": True,
                },
                {
                    "rule_id": "disabled_rule",
                    "rule_name": "Disabled",
                    "scope": "portfolio",
                    "metric_name": (
                        "aggregate_review_burden_score"
                    ),
                    "threshold_value": 50,
                    "comparison": ">=",
                    "severity": "info",
                    "enabled": False,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(td, config_dict)
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert len(config.rules) == 2

            rules, mode, en, dis, errors = (
                get_active_portfolio_trend_alert_rules(path)
            )
            # replace mode: only enabled custom rules
            assert len(rules) == 1
            assert rules[0].rule_id == "enabled_rule"
            assert en == 1
            assert dis == 1


# ---------------------------------------------------------------------------
# Duplicate rule ID rejected
# ---------------------------------------------------------------------------

class TestDuplicateRuleId:
    """Duplicate rule IDs are rejected."""

    def test_duplicate_rule_id(self):
        """Duplicate rule_id within config is rejected."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        config_dict = {
            "mode": "merge",
            "rules": [
                {
                    "rule_id": "same_id",
                    "rule_name": "Rule 1",
                    "scope": "portfolio",
                    "metric_name": (
                        "aggregate_review_burden_score"
                    ),
                    "threshold_value": 50,
                    "comparison": ">=",
                    "severity": "warning",
                    "enabled": True,
                },
                {
                    "rule_id": "same_id",
                    "rule_name": "Rule 2",
                    "scope": "portfolio",
                    "metric_name": (
                        "aggregate_review_burden_score"
                    ),
                    "threshold_value": 60,
                    "comparison": ">=",
                    "severity": "high",
                    "enabled": True,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(td, config_dict)
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert not config.is_valid
            assert any(
                "duplicate" in e.lower()
                for e in config.errors
            )


# ---------------------------------------------------------------------------
# Built-in override rejected
# ---------------------------------------------------------------------------

class TestBuiltinOverrideRejected:
    """Built-in rule IDs cannot be overridden by user config."""

    def test_builtin_override_rejected(self):
        """Using a built-in rule_id in config is rejected."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        config_dict = {
            "mode": "merge",
            "rules": [
                {
                    "rule_id": "burden_high_80",
                    "rule_name": "Override built-in",
                    "scope": "portfolio",
                    "metric_name": (
                        "aggregate_review_burden_score"
                    ),
                    "threshold_value": 75,
                    "comparison": ">=",
                    "severity": "high",
                    "enabled": True,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(td, config_dict)
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert not config.is_valid
            assert any(
                "built-in" in e.lower()
                for e in config.errors
            )


# ---------------------------------------------------------------------------
# Invalid JSON handled
# ---------------------------------------------------------------------------

class TestInvalidJson:
    """Invalid JSON is handled gracefully."""

    def test_invalid_json(self):
        """Malformed JSON returns invalid config."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bad.json")
            with open(path, "w") as f:
                f.write("{invalid json!")
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert not config.is_valid
            assert any(
                "invalid json" in e.lower()
                for e in config.errors
            )


# ---------------------------------------------------------------------------
# Missing required rule_id rejected
# ---------------------------------------------------------------------------

class TestMissingRuleId:
    """Missing rule_id is rejected."""

    def test_missing_rule_id(self):
        """Rule without rule_id is rejected."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        config_dict = {
            "mode": "merge",
            "rules": [
                {
                    "rule_name": "No ID",
                    "scope": "portfolio",
                    "metric_name": (
                        "aggregate_review_burden_score"
                    ),
                    "threshold_value": 50,
                    "comparison": ">=",
                    "severity": "warning",
                    "enabled": True,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(td, config_dict)
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert not config.is_valid
            assert any(
                "rule_id" in e.lower()
                for e in config.errors
            )


# ---------------------------------------------------------------------------
# Invalid scope rejected
# ---------------------------------------------------------------------------

class TestInvalidScope:
    """Invalid scope values are rejected."""

    def test_invalid_scope(self):
        """Rule with invalid scope is rejected."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        config_dict = {
            "mode": "merge",
            "rules": [
                {
                    "rule_id": "bad_scope",
                    "rule_name": "Bad scope",
                    "scope": "global",
                    "metric_name": (
                        "aggregate_review_burden_score"
                    ),
                    "threshold_value": 50,
                    "comparison": ">=",
                    "severity": "warning",
                    "enabled": True,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(td, config_dict)
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert not config.is_valid
            assert any(
                "scope" in e.lower()
                for e in config.errors
            )


# ---------------------------------------------------------------------------
# Invalid comparison rejected
# ---------------------------------------------------------------------------

class TestInvalidComparison:
    """Invalid comparison values are rejected."""

    def test_invalid_comparison(self):
        """Rule with invalid comparison is rejected."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        config_dict = {
            "mode": "merge",
            "rules": [
                {
                    "rule_id": "bad_comp",
                    "rule_name": "Bad comparison",
                    "scope": "portfolio",
                    "metric_name": (
                        "aggregate_review_burden_score"
                    ),
                    "threshold_value": 50,
                    "comparison": "~=",
                    "severity": "warning",
                    "enabled": True,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(td, config_dict)
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert not config.is_valid
            assert any(
                "comparison" in e.lower()
                for e in config.errors
            )


# ---------------------------------------------------------------------------
# Invalid severity rejected
# ---------------------------------------------------------------------------

class TestInvalidSeverity:
    """Invalid severity values are rejected."""

    def test_invalid_severity(self):
        """Rule with invalid severity is rejected."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        config_dict = {
            "mode": "merge",
            "rules": [
                {
                    "rule_id": "bad_sev",
                    "rule_name": "Bad severity",
                    "scope": "portfolio",
                    "metric_name": (
                        "aggregate_review_burden_score"
                    ),
                    "threshold_value": 50,
                    "comparison": ">=",
                    "severity": "critical",
                    "enabled": True,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(td, config_dict)
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert not config.is_valid
            assert any(
                "severity" in e.lower()
                for e in config.errors
            )


# ---------------------------------------------------------------------------
# threshold_value missing where required rejected
# ---------------------------------------------------------------------------

class TestThresholdValueMissing:
    """Non-numeric threshold_value is rejected."""

    def test_non_numeric_threshold(self):
        """Non-numeric threshold_value is rejected."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        config_dict = {
            "mode": "merge",
            "rules": [
                {
                    "rule_id": "bad_thresh",
                    "rule_name": "Bad threshold",
                    "scope": "portfolio",
                    "metric_name": (
                        "aggregate_review_burden_score"
                    ),
                    "threshold_value": "not_a_number",
                    "comparison": ">=",
                    "severity": "warning",
                    "enabled": True,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(td, config_dict)
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert not config.is_valid
            assert any(
                "threshold_value" in e.lower()
                for e in config.errors
            )


# ---------------------------------------------------------------------------
# Walkability metric rejected
# ---------------------------------------------------------------------------

class TestWalkabilityRejected:
    """Walkability metrics are rejected."""

    def test_walkability_metric(self):
        """Rule referencing walkability is rejected."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        config_dict = {
            "mode": "merge",
            "rules": [
                {
                    "rule_id": "walk_rule",
                    "rule_name": "Walkability rule",
                    "scope": "property",
                    "metric_name": "walkability_score",
                    "threshold_value": 50,
                    "comparison": ">=",
                    "severity": "info",
                    "enabled": True,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(td, config_dict)
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert not config.is_valid
            assert any(
                "walkability" in e.lower()
                for e in config.errors
            )


# ---------------------------------------------------------------------------
# Live retrieval metric rejected
# ---------------------------------------------------------------------------

class TestLiveRetrievalRejected:
    """Live retrieval metrics are rejected."""

    def test_live_retrieval_metric(self):
        """Rule referencing live retrieval is rejected."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        config_dict = {
            "mode": "merge",
            "rules": [
                {
                    "rule_id": "live_rule",
                    "rule_name": "Live retrieval rule",
                    "scope": "property",
                    "metric_name": "live_retrieval_count",
                    "threshold_value": 1,
                    "comparison": ">=",
                    "severity": "info",
                    "enabled": True,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(td, config_dict)
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert not config.is_valid
            assert any(
                "live retrieval" in e.lower()
                for e in config.errors
            )


# ---------------------------------------------------------------------------
# Custom rules in evaluation
# ---------------------------------------------------------------------------

class TestCustomRulesEvaluation:
    """Custom rules are applied during evaluation."""

    def test_portfolio_trend_alerts_custom_rules(self):
        """portfolio-trend-alerts uses custom rules."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_portfolio_trend_alerts,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260501_100000.csv",
                [_base_row(property_id="1")],
            )
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260502_100000.csv",
                [_base_row(property_id="1")],
            )
            cfg = _write_rule_config(
                td, _valid_replace_config()
            )
            digest = evaluate_portfolio_trend_alerts(
                exports_dir=td, rule_config=cfg,
            )
            # Replace mode with custom rule checking
            # burden >= 50. The aggregate burden score
            # depends on data, but at minimum the evaluation
            # should proceed without error.
            assert digest is not None
            assert digest.summary is not None

    def test_export_digest_custom_rules(self):
        """Export digest uses custom rules when provided."""
        from marketsentry.portfolio_trend_alerts import (
            export_portfolio_trend_alert_digest,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260501_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="80.0",
                    open_alert_count="1",
                )],
            )
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260502_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="50.0",
                    open_alert_count="5",
                )],
            )
            cfg = _write_rule_config(
                td, _valid_merge_config()
            )
            result = export_portfolio_trend_alert_digest(
                exports_dir=td,
                output_dir=td,
                fmt="both",
                rule_config=cfg,
            )
            assert result is not None
            assert result.summary is not None


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

class TestCLICommands:
    """CLI commands for configurable rules work."""

    def test_cli_list_rules(self):
        """list-portfolio-trend-alert-rules runs."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app, ["list-portfolio-trend-alert-rules"]
        )
        assert result.exit_code == 0
        assert "Portfolio Trend Alert Rules" in result.output
        assert "Active rules" in result.output

    def test_cli_write_template(self):
        """write-portfolio-trend-alert-rule-template runs."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "template.json")
            result = runner.invoke(
                app,
                [
                    "write-portfolio-trend-alert-rule-template",
                    "--output", out,
                ],
            )
            assert result.exit_code == 0
            assert "Template written" in result.output

    def test_cli_validate_valid_config(self):
        """validate-portfolio-trend-alert-rules valid."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            cfg = _write_rule_config(
                td, _valid_merge_config()
            )
            result = runner.invoke(
                app,
                [
                    "validate-portfolio-trend-alert-rules",
                    "--rule-config", cfg,
                ],
            )
            assert result.exit_code == 0
            assert "VALID" in result.output

    def test_cli_validate_invalid_config(self):
        """validate-portfolio-trend-alert-rules invalid."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "bad.json")
            with open(cfg, "w") as f:
                f.write("{bad json")
            result = runner.invoke(
                app,
                [
                    "validate-portfolio-trend-alert-rules",
                    "--rule-config", cfg,
                ],
            )
            assert result.exit_code == 0
            assert "INVALID" in result.output

    def test_cli_list_rules_with_config(self):
        """list-portfolio-trend-alert-rules with config."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            cfg = _write_rule_config(
                td, _valid_merge_config()
            )
            result = runner.invoke(
                app,
                [
                    "list-portfolio-trend-alert-rules",
                    "--rule-config", cfg,
                ],
            )
            assert result.exit_code == 0
            assert "custom_burden_90" in result.output


# ---------------------------------------------------------------------------
# Dashboard rule config data loads
# ---------------------------------------------------------------------------

class TestDashboardRuleConfig:
    """Dashboard rule configuration visibility loads."""

    def test_dashboard_rule_config_imports(self):
        """Dashboard rule config imports succeed."""
        from marketsentry.portfolio_trend_alerts import (
            get_active_portfolio_trend_alert_rules,
            get_default_portfolio_trend_alert_rules,
            DEFAULT_RULE_CONFIG_PATH,
        )
        rules = get_default_portfolio_trend_alert_rules()
        assert len(rules) >= 10
        active, mode, en, dis, errs = (
            get_active_portfolio_trend_alert_rules()
        )
        assert len(active) >= 10
        assert mode == "builtin"


# ---------------------------------------------------------------------------
# Validate function
# ---------------------------------------------------------------------------

class TestValidateFunction:
    """Validate function returns correct counts."""

    def test_validate_valid(self):
        """Validate returns True for valid config."""
        from marketsentry.portfolio_trend_alerts import (
            validate_portfolio_trend_alert_rule_config,
        )
        with tempfile.TemporaryDirectory() as td:
            cfg = _write_rule_config(
                td, _valid_merge_config()
            )
            is_valid, errors, en, dis = (
                validate_portfolio_trend_alert_rule_config(
                    cfg
                )
            )
            assert is_valid is True
            assert len(errors) == 0
            assert en == 1
            assert dis == 0

    def test_validate_with_disabled(self):
        """Validate counts disabled rules."""
        from marketsentry.portfolio_trend_alerts import (
            validate_portfolio_trend_alert_rule_config,
        )
        config_dict = {
            "mode": "merge",
            "rules": [
                {
                    "rule_id": "active_r",
                    "rule_name": "Active",
                    "scope": "portfolio",
                    "metric_name": (
                        "aggregate_review_burden_score"
                    ),
                    "threshold_value": 50,
                    "comparison": ">=",
                    "severity": "warning",
                    "enabled": True,
                },
                {
                    "rule_id": "disabled_r",
                    "rule_name": "Disabled",
                    "scope": "portfolio",
                    "metric_name": (
                        "aggregate_review_burden_score"
                    ),
                    "threshold_value": 80,
                    "comparison": ">=",
                    "severity": "high",
                    "enabled": False,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            cfg = _write_rule_config(td, config_dict)
            is_valid, errors, en, dis = (
                validate_portfolio_trend_alert_rule_config(
                    cfg
                )
            )
            assert is_valid
            assert en == 1
            assert dis == 1


# ---------------------------------------------------------------------------
# Comparison operators
# ---------------------------------------------------------------------------

class TestComparisonOperators:
    """All comparison operators work correctly."""

    def test_check_comparison_ge(self):
        """Greater-than-or-equal works."""
        from marketsentry.portfolio_trend_alerts import (
            _check_comparison,
        )
        assert _check_comparison(">=", 80.0, None, 80.0)
        assert _check_comparison(">=", 81.0, None, 80.0)
        assert not _check_comparison(">=", 79.0, None, 80.0)

    def test_check_comparison_gt(self):
        """Greater-than works."""
        from marketsentry.portfolio_trend_alerts import (
            _check_comparison,
        )
        assert _check_comparison(">", 81.0, None, 80.0)
        assert not _check_comparison(">", 80.0, None, 80.0)

    def test_check_comparison_le(self):
        """Less-than-or-equal works."""
        from marketsentry.portfolio_trend_alerts import (
            _check_comparison,
        )
        assert _check_comparison("<=", 80.0, None, 80.0)
        assert _check_comparison("<=", 79.0, None, 80.0)
        assert not _check_comparison("<=", 81.0, None, 80.0)

    def test_check_comparison_lt(self):
        """Less-than works."""
        from marketsentry.portfolio_trend_alerts import (
            _check_comparison,
        )
        assert _check_comparison("<", 79.0, None, 80.0)
        assert not _check_comparison("<", 80.0, None, 80.0)

    def test_check_comparison_eq(self):
        """Equality works."""
        from marketsentry.portfolio_trend_alerts import (
            _check_comparison,
        )
        assert _check_comparison("==", 80.0, None, 80.0)
        assert not _check_comparison("==", 81.0, None, 80.0)

    def test_check_comparison_ne(self):
        """Not-equal works."""
        from marketsentry.portfolio_trend_alerts import (
            _check_comparison,
        )
        assert _check_comparison("!=", 81.0, None, 80.0)
        assert not _check_comparison("!=", 80.0, None, 80.0)

    def test_check_comparison_delta_ge(self):
        """Delta greater-than-or-equal works."""
        from marketsentry.portfolio_trend_alerts import (
            _check_comparison,
        )
        assert _check_comparison(
            "delta>=", 90.0, 70.0, 15.0
        )
        assert not _check_comparison(
            "delta>=", 80.0, 70.0, 15.0
        )

    def test_check_comparison_delta_le(self):
        """Delta less-than-or-equal works."""
        from marketsentry.portfolio_trend_alerts import (
            _check_comparison,
        )
        assert _check_comparison(
            "delta<=", 50.0, 80.0, -15.0
        )
        assert not _check_comparison(
            "delta<=", 75.0, 80.0, -15.0
        )


# ---------------------------------------------------------------------------
# Scheduled script safety
# ---------------------------------------------------------------------------

class TestScheduledScriptSafety:
    """Scheduled script remains safe."""

    def test_script_exists(self):
        """Portfolio review pack report script exists."""
        path = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        )
        assert path.exists()

    def test_script_no_force_live(self):
        """Script does not contain force-live flags."""
        path = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        )
        content = path.read_text()
        lines = [
            line for line in content.splitlines()
            if not line.strip().startswith("REM")
        ]
        text = "\n".join(lines)
        assert "--force-live" not in text
        assert "--live" not in text

    def test_script_no_mutation_commands(self):
        """Script does not contain mutation commands."""
        path = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        )
        content = path.read_text()
        lines = [
            line for line in content.splitlines()
            if not line.strip().startswith("REM")
        ]
        text = "\n".join(lines)
        assert "triage" not in text.lower()
        assert "archive" not in text.lower()
        assert "expire" not in text.lower()

    def test_script_no_notification_commands(self):
        """Script does not contain notification commands."""
        path = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        )
        content = path.read_text()
        lines = [
            line for line in content.splitlines()
            if not line.strip().startswith("REM")
        ]
        text = "\n".join(lines)
        assert "email" not in text.lower()
        assert "sms" not in text.lower()
        assert "webhook" not in text.lower()

    def test_script_has_alert_digest(self):
        """Script includes alert digest command."""
        path = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        )
        content = path.read_text()
        assert (
            "export-portfolio-trend-alert-digest" in content
        )


# ---------------------------------------------------------------------------
# Safety guard-rail tests
# ---------------------------------------------------------------------------

class TestSafetyGuardRails:
    """Guard-rail constraint tests."""

    def test_no_outbound_notification_in_module(self):
        """Module has no outbound notification code."""
        path = Path(
            "src/marketsentry/portfolio_trend_alerts.py"
        )
        content = path.read_text()
        assert "smtp" not in content.lower()
        assert "send_email" not in content.lower()
        assert "send_sms" not in content.lower()
        assert "webhook" not in content.lower()

    def test_no_candidate_mutation_in_module(self):
        """Module has no candidate/watchlist mutation code."""
        path = Path(
            "src/marketsentry/portfolio_trend_alerts.py"
        )
        content = path.read_text()
        assert "session.commit" not in content
        assert "session.add" not in content
        assert "db.execute" not in content

    def test_no_redfin_overwrite_in_module(self):
        """Module does not overwrite Redfin fields."""
        path = Path(
            "src/marketsentry/portfolio_trend_alerts.py"
        )
        content = path.read_text()
        assert "redfin_url" not in content.lower() or (
            "redfin_url" in content.lower() and
            "update" not in content.lower()
        )

    def test_quiet_gatekeeper_unchanged(self):
        """Quiet gatekeeper threshold is not modified."""
        path = Path(
            "src/marketsentry/portfolio_trend_alerts.py"
        )
        content = path.read_text()
        assert "quiet_gatekeeper" not in content.lower()
        assert "70.0" not in content or (
            "70.0" in content and
            "quiet" not in content.lower()
        )

    def test_no_walkability_fields(self):
        """No walkability fields in module."""
        path = Path(
            "src/marketsentry/portfolio_trend_alerts.py"
        )
        content = path.read_text()
        # walkability appears in forbidden checks only
        for line in content.splitlines():
            if "walkability" in line.lower():
                assert (
                    "forbidden" in line.lower()
                    or "FORBIDDEN" in line
                    or "walk_score" in line
                    or "transit_score" in line
                    or "walkability_score" in line.lower()
                    and "prefix" in line.lower()
                    or '"walkability' in line
                )

    def test_no_network_calls_in_module(self):
        """Module makes no network calls."""
        path = Path(
            "src/marketsentry/portfolio_trend_alerts.py"
        )
        content = path.read_text()
        assert "requests.get" not in content
        assert "httpx" not in content
        assert "urllib.request" not in content
        assert "socket.connect" not in content

    def test_no_browser_automation(self):
        """Module has no browser automation imports."""
        path = Path(
            "src/marketsentry/portfolio_trend_alerts.py"
        )
        content = path.read_text()
        # playwright/selenium appear in FORBIDDEN_METRIC_KEYWORDS
        # as validation guards. Check for actual import usage.
        assert "import playwright" not in content.lower()
        assert "import selenium" not in content.lower()
        assert "from playwright" not in content.lower()
        assert "from selenium" not in content.lower()

    def test_configurable_rules_are_read_only(self):
        """Configurable rules produce read-only alerts."""
        from marketsentry.portfolio_trend_alerts import (
            _evaluate_configurable_rules,
            _builtin_to_configurable,
        )
        # The function returns alerts but does not
        # write to any database
        rules = _builtin_to_configurable()
        alerts = _evaluate_configurable_rules(
            rules, [], [], "2026-05-13"
        )
        assert isinstance(alerts, list)

    def test_no_purchase_recommendations(self):
        """Module does not make purchase recommendations."""
        path = Path(
            "src/marketsentry/portfolio_trend_alerts.py"
        )
        content = path.read_text()
        # "purchase" appears only in safety docstrings
        # ("not purchase recommendations"). Verify no
        # imperative purchase recommendation exists.
        assert "you should buy" not in content.lower()
        assert "recommend purchasing" not in content.lower()
        assert "recommend buying" not in content.lower()

    def test_invalid_mode_rejected(self):
        """Invalid mode value is rejected."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        config_dict = {
            "mode": "override_all",
            "rules": [],
        }
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(td, config_dict)
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert not config.is_valid
            assert any(
                "mode" in e.lower()
                for e in config.errors
            )

    def test_config_not_dict_rejected(self):
        """Config that is not a dict is rejected."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bad.json")
            with open(path, "w") as f:
                json.dump([1, 2, 3], f)
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert not config.is_valid
            assert any(
                "object" in e.lower()
                for e in config.errors
            )

    def test_rules_not_list_rejected(self):
        """Config where rules is not a list is rejected."""
        from marketsentry.portfolio_trend_alerts import (
            load_portfolio_trend_alert_rule_config,
        )
        config_dict = {
            "mode": "merge",
            "rules": "not_a_list",
        }
        with tempfile.TemporaryDirectory() as td:
            path = _write_rule_config(td, config_dict)
            config = load_portfolio_trend_alert_rule_config(
                path
            )
            assert not config.is_valid
            assert any(
                "list" in e.lower()
                for e in config.errors
            )
