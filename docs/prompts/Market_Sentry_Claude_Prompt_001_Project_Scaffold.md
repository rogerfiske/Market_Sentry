# Claude Code Prompt 001 - Market_Sentry Project Scaffold

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository:

https://github.com/rogerfiske/Market_Sentry

Project mission:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It begins with Redfin candidate discovery, stages candidates for user review, and later monitors selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, and cross-site/county validation.

Critical domain rules:

1. Effective DOM measures property-level market exposure across listing, removal, and relisting events within a defined lookback window, excluding periods reset by confirmed ownership transfer.
2. Quiet Score is the gatekeeper. Reject or heavily downgrade if Quiet Score is below threshold, even when Vibrancy is low.
3. Target is very high Quiet and very low Vibrancy.
4. Low Vibrancy alone is not sufficient.
5. Any mention of gas means the property has natural gas service/supply.
6. Walkability-type information is excluded from the initial scope.
7. Use neutral language. Do not infer seller intent.
8. The workflow is human-in-the-loop: candidate review queue first, then user-selected watched properties.

Your task for Prompt 001:

Create the initial local Python project scaffold only. Do not implement live scraping yet.

Required deliverables:

1. Create or update the following files:

```text
README.md
PRD.md
Architecture.md
requirements.txt
.env.example
.gitignore
pyproject.toml
```

2. Create this directory structure:

```text
data/
  raw/
  processed/
  exports/
  imports/
db/
logs/
docs/
  prompts/
  decisions/
  examples/
src/
  Market_Sentry/
    __init__.py
    cli.py
    config.py
    logging_config.py
    models.py
    database.py
    schema.py
    normalization.py
    gas_detection.py
    quiet_vibrancy.py
    effective_dom.py
    scoring.py
    review_export.py
    review_import.py
tests/
  test_gas_detection.py
  test_quiet_vibrancy.py
  test_effective_dom.py
  test_scoring.py
  test_database.py
```

3. Implement only foundational code:

- A minimal CLI entry point.
- A config loader.
- Basic logging setup.
- Basic data models using type hints.
- Basic gas detection function.
- Basic Quiet/Vibrancy gatekeeper function.
- Basic placeholder Effective DOM calculation function.
- Basic placeholder scoring function.
- Unit tests for the basic functions.

4. Code standards:

- Python 3.11+
- PEP8 compliant.
- Type hints required.
- Docstrings required for all functions.
- Remove unused imports.
- Keep modules small and readable.

5. Database:

- Create schema definitions or SQL strings for future tables.
- Implement an init_db function that creates the SQLite database and initial tables.
- No live data ingestion yet.

6. Tests:

Run pytest and ensure all tests pass.

7. README:

Include:

- Project purpose
- Current milestone scope
- Setup instructions
- CLI usage
- Domain rules
- Next planned milestone

Quality gates:

- Project imports cleanly.
- CLI can run.
- SQLite init works.
- Unit tests pass.
- No scraping or network calls implemented in this milestone.

Completion report required:

When finished, provide:

1. Summary of what you implemented.
2. Files created or modified.
3. Exact commands run.
4. Test results.
5. Any assumptions made.
6. Any blockers or risks.
7. Recommended next step.
8. Git commit hash after committing and pushing completed changes to origin/main.

Important:

After all quality gates pass, commit and push the completed story changes to origin/main and include the commit hash in your completion report.
