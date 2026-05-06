# Decision 013: Live Retrieval Strategy and Compliance Adapters

## Status

Accepted

## Context

Market_Sentry needs to eventually retrieve data from real estate sites (Redfin, Zillow, Realtor.com, Homes.com, Compass) and county recorder/assessor sites. Before implementing any live network access, a compliance-aware architecture must be in place to ensure retrieval is safe, explicit, auditable, rate-limited, and disabled by default.

## Decision

Implement a source adapter architecture with compliance guardrails and dry-run preview capability before any live retrieval. Live retrieval is disabled by default and requires explicit environment variable opt-in. The current milestone provides only adapter design, compliance checking, and dry-run commands.

## Why Compliance Adapters Come Before Live Retrieval

1. **Safety first.** Establishing compliance infrastructure before live access prevents accidental or uncontrolled retrieval.
2. **Dry-run validation.** Users can preview what would be retrieved and verify compliance rules before enabling live access.
3. **Audit trail.** Retrieval audit logging is in place before any network calls occur.
4. **Architecture validation.** The adapter pattern can be tested and refined with dry-run and fixture modes before adding network code.

## Why Dry-Run Comes First

1. Dry-run commands validate URL parsing, compliance checking, and preview generation without risk.
2. Users can verify that compliance rules correctly block unauthorized access.
3. The dry-run output serves as documentation of what live retrieval would do.
4. Dry-run tests can run in CI without network access.

## Why live_http Is Disabled by Default

1. **Conservative default.** No network calls unless the user explicitly opts in.
2. **Compliance awareness.** Users must configure User-Agent, contact email, and source allowlists before enabling.
3. **Rate limiting.** Default rate limits are conservative (6 requests/minute).
4. **Audit requirement.** All retrieval decisions are logged before any live access.

## Why Authorized APIs/Feeds Are Preferred

1. Official APIs provide structured data with explicit permission.
2. API access comes with documented rate limits and terms.
3. APIs eliminate HTML parsing fragility.
4. API access reduces legal and compliance risk.
5. The adapter architecture supports swapping between modes.

## Why Source Adapters Are Swappable

1. Different sources may require different retrieval strategies.
2. A source may transition from fixture → API → HTTP over time.
3. Testing is easier when adapters can be mocked or stubbed.
4. County sources have different compliance requirements than real estate listing sites.

## Why No Browser Automation or Bypass Is Implemented

1. Browser automation (Playwright, Selenium) is heavyweight and fragile.
2. Bypassing anti-bot protections violates site terms of service.
3. CAPTCHAs, login walls, and paywalls are access controls that must be respected.
4. Simple HTTP requests (when authorized) are more reliable and auditable.

## Consequences

- Users can preview retrieval behavior safely with dry-run commands.
- The compliance infrastructure is in place for future live retrieval.
- All retrieval decisions are audited regardless of mode.
- Live retrieval requires explicit, deliberate configuration.
- The adapter pattern supports future authorized API integrations.
- No network calls are performed in the current milestone.
