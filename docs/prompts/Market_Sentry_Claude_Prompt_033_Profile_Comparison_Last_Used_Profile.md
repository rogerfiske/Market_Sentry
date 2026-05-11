# Claude Code Prompt 033 - Alert Expiration Profile Comparison and Last-Used Profile Persistence

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository:

https://github.com/rogerfiske/Market_Sentry

Local project folder:

C:\Users\Minis\CascadeProjects\Market_Sentry

Current accepted milestones:

- Milestone 1 scaffold complete at commit c8599761be1aeda80b075cf668c61970e587ebe7
- Milestone 2 candidate review queue and watchlist promotion complete at commit 5da7747a44069696189d1abb8057ee23f17d8754
- Milestone 3 Redfin discovery adapter foundation complete at commit 91eac91085609c38f150881bf35e5a22d1f6bdf0
- Milestone 4 Redfin detail parser and candidate enrichment complete at commit dafb63d
- Milestone 5 Effective DOM engine and candidate scoring report complete at commit 52ea72d
- Milestone 6 cross-site enrichment foundation stabilized and accepted at commit 01b6887
- Milestone 7 watchlist monitoring snapshots and change detection complete at commit 23ac2b5
- Milestone 8 county recorder and assessor verification foundation complete at commit 89ce91a
- Milestone 9 Effective DOM v2 county-verified reset integration complete at commit 0e83285
- Milestone 10 Effective DOM v2 operational integration complete at commit 44b655d
- Milestone 11 end-to-end operating workflow and runbook complete at commit 6cf5627
- Prompt 011A export path stabilization complete at commit 4475634
- Milestone 12 local dashboard and report viewer complete at commit 6cb30f1
- Milestone 13 Windows Task Scheduler automation complete at commit deaa042
- Milestone 14 live retrieval strategy and compliance adapters complete at commit ee7e81f
- Milestone 15 retrieval safety enforcement and fixture capture queue complete at commit e4010d8
- Milestone 16 Redfin Live HTTP Retrieval Phase 1 complete at commit d8ed591
- Milestone 17 Redfin retrieved fixture processing pipeline complete at commit e41e5e4
- Milestone 18 Redfin pending capture batch retrieval orchestrator complete at commit 2d420d7
- Milestone 19 Redfin batch retrieval approval workflow complete at commit 66628f6
- Milestone 20 retrieval operations dashboard integration complete at commit 9df9300
- Milestone 21 retrieval operations aging, alerts, and health checks complete at commit c92f687
- Milestone 22 cross-site adapter parity and manual fixture workflow complete at commit 1e3235c
- Milestone 23 cross-site parser quality and fixture corpus expansion complete at commit 3b1470a
- Milestone 24 confidence-weighted cross-site comparison analytics complete at commit 788ac84
- Milestone 25 cross-site analytics trend snapshots complete at commit 3322f92
- Milestone 26 cross-site trend alerts and watchlist monitoring integration complete at commit 67d2265
- Milestone 27 cross-site alert aggregation and historical pattern analysis complete at commit 1cfaf34
- Milestone 28 cross-site alert triage workflow complete at commit b044306
- Milestone 29 scheduled triage reminder and alert hygiene reports complete at commit a752068
- Milestone 30 opt-in resolved alert archive policy workflow complete at commit e5261c0
- Milestone 31 configurable alert expiration rules and operator approval gates complete at commit d9fbe84
- Milestone 32 user-defined alert expiration profiles complete at commit c211670

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Review the current codebase through commit c211670.
8. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
9. Keep PRD.md and Architecture.md in the project root.
10. Use src/marketsentry/ as the Python package path.
11. Do not move PRD.md or Architecture.md into docs/.
12. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
13. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
14. Do not implement new Redfin live retrieval behavior in this milestone.
15. Do not run any live network calls in tests.
16. Do not make scheduled tasks run live retrieval by default.
17. Do not add walkability parsing or walkability fields.
18. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 33 should add profile comparison views and local last-used profile persistence for cross-site alert expiration policy.

This milestone should NOT add live retrieval.

This milestone should NOT broaden scraping.

This milestone should NOT change the Quiet Score gatekeeper.

This milestone should NOT automatically apply expiration actions.

The goal is to help the user choose the right alert expiration profile safely:

- compare built-in and custom profiles side-by-side
- show how many alerts each profile would affect
- show proposed archive/review/keep counts per profile
- show differences between two profiles
- export comparison reports
- remember the last profile used locally
- use last-used profile as a convenience default only
- preserve approval-gated mutation workflow

This is a local convenience/reporting milestone. It must not change watchlist status automatically, must not overwrite Redfin source-of-truth fields, and must not infer seller intent.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It uses a human-in-the-loop, fixture-first workflow to observe candidate and watched properties using Effective DOM v1/v2, Churn Index, Quiet/Vibrancy gatekeeper logic, gas evidence, garage spaces, cross-site validation, county verification, local reports, dashboard views, Windows Task Scheduler support, and compliance-aware retrieval operations.

Critical domain rules:

1. Effective DOM v1 is listing-history-derived exposure without county reset integration.
2. Effective DOM v2 applies county-confirmed ownership transfer as a reset boundary when appropriate.
3. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
4. Churn Index remains reportable even when Effective DOM is reset.
5. Quiet Score is the gatekeeper.
6. Target is very high Quiet and very low Vibrancy.
7. Any mention of gas means the property has natural gas supply/service.
8. Walkability-type information is excluded from the initial scope.
9. Use neutral language. Do not infer seller intent.
10. Reports are analytical aids, not purchase recommendations.
11. Profile comparison may generate preview data only; actions require explicit approval import.
12. Last-used profile persistence must not apply actions automatically or change watchlist status.

Your task for Prompt 033:

Implement Alert Expiration Profile Comparison and Last-Used Profile Persistence v1.

## 1. Profile comparison module

Extend `src/marketsentry/cross_site_alert_expiration_policy.py` or create a helper module, for example:

```text
src/marketsentry/cross_site_alert_expiration_profile_comparison.py
```

Required models:

- CrossSiteAlertExpirationProfileComparisonRow
- CrossSiteAlertExpirationProfileComparisonResult
- CrossSiteAlertExpirationProfileDiff
- CrossSiteAlertExpirationProfilePreference
- CrossSiteAlertExpirationProfilePreferenceResult

Required functions:

- compare_alert_expiration_profiles(...)
- compare_two_alert_expiration_profiles(...)
- export_alert_expiration_profile_comparison(...)
- get_profile_candidate_counts(...)
- summarize_profile_differences(...)
- load_last_used_expiration_profile(...)
- save_last_used_expiration_profile(...)
- clear_last_used_expiration_profile(...)

## 2. Profile comparison behavior

Compare profiles by running preview logic for each profile without mutations.

For each profile, compute:

- profile_name
- profile_source: built_in or user_config
- total_candidates
- proposed_archive_count
- proposed_review_count
- proposed_keep_count
- high_critical_review_count
- no_archive_excluded_count if available
- affected_property_count
- oldest_candidate_age_days
- youngest_candidate_age_days
- rule_count
- validation_status
- notes

For two-profile diff, compute:

- profile_a
- profile_b
- candidate_count_delta
- archive_count_delta
- review_count_delta
- keep_count_delta
- properties_only_in_a
- properties_only_in_b
- alerts_only_in_a
- alerts_only_in_b
- common_alerts_with_different_actions
- summary_text

Use neutral wording.

## 3. Last-used profile persistence

Store local preference in a non-secret JSON file.

Suggested path:

```text
config/alert_expiration_profile_preference.json
```

Suggested contents:

```json
{
  "last_used_profile": "standard",
  "profile_config_path": "config/alert_expiration_profiles.json",
  "saved_at": "2026-05-11T15:00:00",
  "notes": "Local convenience setting only; does not apply actions."
}
```

Required behavior:

- Loading missing preference file returns a safe default, probably `standard`.
- Saving preference validates the profile exists before saving.
- Preference does not apply actions.
- Preference must not cause scheduled mutation.
- Preference should be used only as CLI/dashboard convenience default where appropriate.
- Invalid preference file should fail safely and fall back to built-in standard with warning.

## 4. CLI commands

Add CLI commands:

```text
marketsentry compare-cross-site-alert-expiration-profiles
marketsentry export-cross-site-alert-expiration-profile-comparison
marketsentry set-cross-site-alert-expiration-profile
marketsentry get-cross-site-alert-expiration-profile
marketsentry clear-cross-site-alert-expiration-profile
```

### compare-cross-site-alert-expiration-profiles

Options:

- --profile-config optional
- --profiles optional comma-separated list
- --db

Output:

- one row per profile
- candidate/action counts
- no mutations

### export-cross-site-alert-expiration-profile-comparison

Options:

- --profile-config optional
- --profiles optional comma-separated list
- --output-dir
- --db

Output:

```text
data/exports/cross_site_alert_expiration_profile_comparison_YYYYMMDD_HHMMSS.csv
```

### set-cross-site-alert-expiration-profile

Options:

- --profile required
- --profile-config optional
- --preference-path optional default config/alert_expiration_profile_preference.json

Behavior:

- validate profile exists
- save preference
- no mutations to alerts

### get-cross-site-alert-expiration-profile

Options:

- --preference-path optional
- --profile-config optional

Output:

- last-used profile
- config path if any
- validation status

### clear-cross-site-alert-expiration-profile

Options:

- --preference-path optional

Behavior:

- remove preference file or reset to standard
- no alert mutation

## 5. Existing CLI default behavior

Where appropriate, update Milestone 31 commands so if `--profile` is omitted:

- use last-used profile if preference exists and is valid
- otherwise use `standard`

Commands to consider:

- preview-cross-site-alert-expiration-policy
- export-cross-site-alert-expiration-approval
- cross-site-alert-expiration-summary

Do not let invalid preference break these commands. Fall back safely to `standard` and show a warning.

## 6. Dashboard integration

Update Cross-Site Alert Expiration Policy subsection to show:

- last-used profile
- preference validation status
- comparison table for built-in profiles
- custom profiles included if config valid
- optional profile diff summary if straightforward
- latest comparison export if available

Dashboard remains read-only.

Do not add dashboard mutation actions.

## 7. Tests

Add or update tests for:

- compare built-in profiles
- compare profiles with custom config
- compare selected subset of profiles
- profile comparison row counts
- two-profile diff candidate/action deltas
- export comparison CSV
- load missing preference returns standard
- save valid last-used profile
- save invalid profile rejected
- load invalid preference falls back safely
- clear preference
- CLI compare profiles
- CLI export profile comparison
- CLI set profile
- CLI get profile
- CLI clear profile
- existing preview command uses valid last-used profile when --profile omitted
- existing preview command falls back to standard when preference invalid
- dashboard comparison data loads
- no auto-apply behavior
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-32 tests still pass

All tests must pass.

## 8. Documentation

Update README.md and docs/RUNBOOK.md with a "Profile Comparison and Last-Used Profile" section.

Update docs/ALERT_EXPIRATION_PROFILES.md with:

- compare profiles command
- export comparison command
- set/get/clear profile commands
- preference file path and meaning
- fallback behavior
- reminder that preference does not apply actions

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with a short section on choosing profiles safely.

Create design decision note:

```text
docs/decisions/032-alert-expiration-profile-comparison-preferences.md
```

Explain:

- why comparison is added before more automation
- why last-used profile is local convenience only
- why invalid preference falls back to standard
- why profile preference cannot apply actions
- why watchlist state is not automatically changed
- why Quiet Score gatekeeper is unchanged
- why walkability remains excluded

## 9. Code standards

- Python 3.11+
- PEP8 compliant.
- Type hints required.
- Docstrings required for all functions.
- Remove unused imports.
- Keep modules small and readable.
- Use Python standard library JSON support.
- No browser automation.
- No Playwright/Selenium.
- No bypassing CAPTCHAs, paywalls, login walls, anti-bot protections, or technical access controls.
- No network calls in tests.
- Preserve source URLs and timestamps for auditability.
- Avoid inaccurate Claude co-authorship metadata.
- Use neutral language.
- Do not make purchase recommendations.
- Do not add walkability parsing or walkability fields.

## Quality gates

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works for fresh database.
- Existing custom profile loading works.
- Existing expiration profile preview/export/import works.
- Profile comparison works.
- Last-used profile preference works.
- Dashboard profile comparison section loads.
- No Redfin source-of-truth fields are overwritten.
- Quiet gatekeeper remains unchanged.
- No real network calls are performed in tests.
- No scheduled task invokes live retrieval or expiration mutation.
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
8. Example compare-cross-site-alert-expiration-profiles output.
9. Example profile comparison CSV path and row count.
10. Example set/get/clear profile output.
11. Example fallback behavior for invalid preference.
12. Dashboard profile comparison/preference visibility added.
13. Confirmation that profile comparison does not auto-apply actions.
14. Confirmation that profile preference does not change watchlist status.
15. Confirmation that profile comparison does not overwrite Redfin source-of-truth fields.
16. Confirmation that Quiet Score gatekeeper remains unchanged.
17. Confirmation that walkability fields were not added.
18. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
19. Confirmation that tests perform no real network calls.
20. Recommended next implementation step.
21. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 33 complete until all tests pass.
