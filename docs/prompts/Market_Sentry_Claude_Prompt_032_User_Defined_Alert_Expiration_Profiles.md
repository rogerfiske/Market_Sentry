# Claude Code Prompt 032 - User-Defined Alert Expiration Profiles

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Review the current codebase through commit d9fbe84.
7. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
8. Keep PRD.md and Architecture.md in the project root.
9. Use src/marketsentry/ as the Python package path.
10. Do not move PRD.md or Architecture.md into docs/.
11. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
12. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
13. Do not implement new Redfin live retrieval behavior in this milestone.
14. Do not run any live network calls in tests.
15. Do not make scheduled tasks run live retrieval by default.
16. Do not add walkability parsing or walkability fields.
17. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 32 should add user-defined local expiration profiles for cross-site alert expiration policy.

This milestone should NOT add live retrieval.

This milestone should NOT broaden scraping.

This milestone should NOT change the Quiet Score gatekeeper.

This milestone should NOT automatically apply expiration actions.

The goal is to let the user define custom local alert expiration profiles in a human-editable config file while preserving Milestone 31’s safe approval-gated workflow:

- built-in profiles still work
- custom profiles can be loaded from local config
- custom profiles are validated before use
- invalid profiles are rejected with clear errors
- preview/export/import remain explicit and approval-gated
- dashboard and CLI can show both built-in and custom profiles
- scheduled scripts must not apply mutations

This is an operational alert-state policy workflow only. It must not change watchlist status automatically, must not overwrite Redfin source-of-truth fields, and must not infer seller intent.

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
11. User-defined expiration profiles may generate candidates only; actions require explicit approval import.
12. Expiration policy workflow must not change watchlist status automatically.

Your task for Prompt 032:

Implement User-Defined Alert Expiration Profiles v1.

## 1. Custom profile configuration

Add support for loading custom expiration profiles from a local JSON file.

Suggested path:

```text
config/alert_expiration_profiles.json
```

Do not require this file to exist.

If absent, built-in profiles from Milestone 31 must still work.

Create an example config:

```text
config/alert_expiration_profiles.example.json
```

Do not store user-specific secrets in the config.

## 2. Config format

Example:

```json
{
  "profiles": [
    {
      "profile_name": "my_custom_review",
      "description": "Custom local review profile",
      "rules": [
        {
          "rule_name": "resolved_archive_75d",
          "current_status": "resolved",
          "severity": ["info", "warning", "high", "critical"],
          "min_age_days": 75,
          "proposed_action": "archive",
          "exclude_no_archive": true
        },
        {
          "rule_name": "acknowledged_review_21d",
          "current_status": "acknowledged",
          "severity": ["info", "warning", "high", "critical"],
          "min_age_days": 21,
          "proposed_action": "review",
          "exclude_no_archive": false
        }
      ]
    }
  ]
}
```

Allowed `current_status` values:

- open
- acknowledged
- resolved
- archived

Allowed severity values:

- info
- warning
- high
- critical
- any

Allowed proposed_action values:

- archive
- review
- keep
- reopen_review

Validation rules:

- profile_name required, unique, lowercase/snake-ish recommended
- rule_name required, unique within profile
- min_age_days integer >= 0
- high/critical open alerts may only propose review or keep
- archived alerts may only propose keep or review
- no rules may propose deleting anything
- no rule may change watchlist status
- no live retrieval configuration allowed in this file

## 3. Profile loader module

Extend Milestone 31 module or create helper module.

Suggested functions:

- load_user_expiration_profiles(config_path: Path | str | None = None)
- validate_expiration_profile_config(...)
- merge_builtin_and_user_profiles(...)
- write_example_expiration_profile_config(...)
- get_expiration_profile_by_name(...)

Required behavior:

- Built-in profiles are always available.
- User profiles are optional.
- Duplicate user profile names should be rejected unless an explicit `allow_override=False` policy is changed; default reject.
- User profile names must not silently override built-in profiles.
- Validation errors must be clear and actionable.
- Loading invalid config should not break built-in profiles when CLI lists profiles unless the user explicitly asks to use that invalid profile; choose safe behavior and document it.

## 4. CLI updates

Update existing Milestone 31 CLI commands to support:

```text
--profile-config config/alert_expiration_profiles.json
```

Commands:

- list-cross-site-alert-expiration-profiles
- preview-cross-site-alert-expiration-policy
- export-cross-site-alert-expiration-approval
- cross-site-alert-expiration-summary

Add new command:

```text
marketsentry write-alert-expiration-profile-template
```

Options:

- --output config/alert_expiration_profiles.example.json
- --overwrite optional default false

Behavior:

- writes example JSON config
- does not overwrite existing file unless --overwrite true
- prints path

## 5. Dashboard integration

Update Cross-Site Alert Expiration Policy dashboard subsection to show:

- built-in profiles
- detected custom profiles if config file exists
- validation status of custom profile config
- selected/default profile summary if available
- candidate count using default/built-in standard profile unless user config is valid and explicitly selected by a future mechanism

Dashboard remains read-only.

Do not add dashboard mutation actions.

## 6. Documentation

Update README.md and docs/RUNBOOK.md with a "User-Defined Alert Expiration Profiles" section.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with:

- how to write the example config
- config file path
- profile/rule fields
- validation rules
- how to preview custom profile
- how to export approval CSV using custom profile
- reminder that actions still require approval import

Create:

```text
docs/ALERT_EXPIRATION_PROFILES.md
```

Explain:

- built-in profiles
- custom config format
- validation rules
- CLI commands
- examples
- safety limits
- no auto-apply behavior

Create design decision note:

```text
docs/decisions/031-user-defined-alert-expiration-profiles.md
```

Explain:

- why custom profiles are local config
- why invalid configs are rejected
- why built-in profiles remain available
- why user profiles cannot silently override built-ins
- why approval gates remain required
- why watchlist state is not automatically changed
- why Quiet Score gatekeeper is unchanged
- why walkability remains excluded

## 7. Tests

Add or update tests for:

- built-in profiles still load without config
- missing config does not error
- example config writer creates file
- example config writer refuses overwrite by default
- valid user profile loads
- multiple user profiles load
- duplicate user profile names rejected
- user profile cannot override built-in profile
- invalid JSON handled clearly
- missing profile_name rejected
- missing rule_name rejected
- invalid status rejected
- invalid severity rejected
- invalid proposed_action rejected
- negative min_age_days rejected
- high/critical open archive rule rejected
- archived alert mutation rule rejected
- merge builtin and user profiles
- get_expiration_profile_by_name built-in
- get_expiration_profile_by_name custom
- preview policy with custom profile
- export approval CSV with custom profile
- CLI list profiles with config
- CLI write template
- CLI preview custom profile
- CLI export custom profile
- dashboard custom profile validation data loads
- no auto-apply behavior
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-31 tests still pass

All tests must pass.

## 8. Code standards

- Python 3.11+
- PEP8 compliant.
- Type hints required.
- Docstrings required for all functions.
- Remove unused imports.
- Keep modules small and readable.
- Use Python standard library JSON support unless a dependency already exists; do not add a YAML dependency unless necessary.
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
- Existing cross-site alert archive workflow works.
- Existing expiration profile preview/export/import works.
- Custom profile loading works.
- Invalid custom configs fail safely.
- Dashboard expiration profile section loads.
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
8. Example alert_expiration_profiles.example.json content/path.
9. Example list profiles output showing built-in and custom profiles.
10. Example preview using custom profile.
11. Example approval CSV export using custom profile.
12. Dashboard custom profile visibility added.
13. Validation errors handled.
14. Confirmation that custom profiles do not auto-apply actions.
15. Confirmation that custom profiles do not overwrite Redfin source-of-truth fields.
16. Confirmation that Quiet Score gatekeeper remains unchanged.
17. Confirmation that walkability fields were not added.
18. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
19. Confirmation that tests perform no real network calls.
20. Recommended next implementation step.
21. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 32 complete until all tests pass.
