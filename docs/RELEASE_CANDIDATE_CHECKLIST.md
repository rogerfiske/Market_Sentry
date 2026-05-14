# Release Candidate Checklist

Generated: 2026-05-14 08:40:26
Commit: de48925
Branch: main

## Operator Acceptance Checklist

| Status | ID | Description | Detail |
|--------|----|-------------|--------|
| PASS | doc_prd | PRD.md present | PRD.md found |
| PASS | doc_arch | Architecture.md present | Architecture.md found |
| PASS | doc_readme | README.md present | README.md found |
| PASS | doc_runbook | docs/RUNBOOK.md present | docs/RUNBOOK.md found |
| PASS | doc_scheduler | Windows Task Scheduler guide present | docs/WINDOWS_TASK_SCHEDULER.md found |
| PASS | doc_ops_bundle | Local Operations Bundle docs present | docs/LOCAL_OPERATIONS_BUNDLE.md found |
| PASS | cmd_bundle | local-operations-bundle command available | CLI app imports cleanly |
| PASS | cmd_dashboard | dashboard command available | CLI app imports cleanly |
| PASS | cmd_smoke | smoke test command available | CLI app imports cleanly |
| PASS | script_safe | Safe scheduled scripts present | Scripts found |
| PASS | script_no_force_live | No scheduled script uses --force-live | No --force-live found |
| PASS | live_retrieval_disabled | Live retrieval disabled by default | Live retrieval requires explicit opt-in |
| PASS | no_outbound_notification | No outbound notification behavior | No SMTP/Gmail/Outlook/webhook/SMS code |
| PASS | no_credentials | No credentials required | No credential storage or requests |
| PASS | quiet_gatekeeper | Quiet Score gatekeeper unchanged | Threshold remains at 70.0 |
| PASS | walkability_excluded | Walkability excluded | No walkability fields present |
| N/C | tests_passing | Tests passing status | Run pytest to verify |
| PASS | db_init | Database init works | Database init succeeds with temp DB |
| PASS | exports_dir | Local-only report exports work | data/exports exists |

## Recommended Actions

- [tests_passing] Run: python -m pytest --tb=short --no-cov -q

## Validation Results

- [PASS] required_files: All required files present
- [PASS] ops_bundle_builds: Bundle built: 48 commands
- [PASS] smoke_test: Smoke: 6 checks, 0 failures
- [PASS] safety_audit: Safety: 7 checks, 0 failures
- [WARN] config_templates: Missing: config/portfolio_trend_alert_rules.example.json
- [PASS] release_docs: Release docs present
- [PASS] rc_module_safety: No forbidden patterns found

## GitHub Release Preparation

- [ ] All tests pass
- [ ] Documentation up to date
- [ ] Operations bundle runs cleanly
- [ ] Smoke test passes
- [ ] Create GitHub release with version tag
- [ ] Attach release notes
