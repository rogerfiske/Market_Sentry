# Decision 014: Retrieval Safety Enforcement and Fixture Capture Queue

## Date

2026-05-06

## Status

Accepted (Milestone 15)

## Context

Milestone 14 introduced the compliance-aware source adapter architecture with dry-run previews. Milestone 15 hardens this foundation by adding retrieval policy checks, offline robots parsing, rate limiting, dry-run approval gating, and a fixture capture queue.

## Decisions

### Why safety enforcement is added before live retrieval

Live retrieval will eventually require HTTP requests to external sites. Before implementing that, all safety guardrails must be in place and tested. This ensures that when live retrieval is added in a future milestone, it will be safe by default.

### Why robots policy is local/offline in this milestone

Fetching robots.txt from the internet would itself be a network call, which contradicts the no-network-calls constraint. Instead, we provide an interface that parses locally saved robots.txt files. Users can save a site's robots.txt manually to `data/policies/robots/` for offline checking.

### Why rate limiting is implemented before HTTP

Rate limiting logic is deterministic and testable without network calls. Implementing it now means that when live retrieval is enabled later, rate limits will already be enforced from the start.

### Why dry-run approval is required

Requiring a dry-run before live retrieval ensures that every live request has been previewed first. This prevents accidental or automated live requests. The approval record provides an audit trail of what was previewed and when.

### Why fixture capture queue remains the primary workflow

Manual fixture capture is the safest and most compliant workflow. The queue formalizes this by telling users exactly what to save and where. This is the recommended workflow even if live retrieval is implemented later.

## Consequences

- All safety guardrails are tested and in place before live retrieval.
- The fixture capture queue provides a structured manual workflow.
- Future live retrieval implementation can build on proven safety infrastructure.
- No network calls are performed in this milestone.
