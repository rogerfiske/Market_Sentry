# MarketSentry PRD

## 1. Product name

MarketSentry

## 2. Product summary

MarketSentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It starts with filtered Redfin search pages, stages discovered homes for human review, and then monitors user-selected properties over time.

The system's differentiating metric is Effective DOM.

Effective DOM measures property-level market exposure across listing, removal, and relisting events within a defined lookback window, excluding periods reset by confirmed ownership transfer.

MarketSentry is not intended to infer seller intent. It uses neutral terms such as listing churn, non-closing relist cycle, DOM reset pattern, sale/rent alternation, and pre-portal exposure.

## 3. Current user objective

The user is observing the Temecula/Murrieta real-estate market with a possible purchase horizon of approximately 12 months. The first system should support disciplined market observation, not automatic purchasing decisions.

## 4. Primary source workflow

### 4.1 Candidate discovery

Search Redfin first using the user's filtered Temecula/Murrieta search paths.

### 4.2 Detail extraction

If a Redfin candidate is found, collect:

- Redfin URL
- Address
- City
- ZIP
- Price
- Beds
- Baths
- Square feet
- Lot size
- Displayed DOM
- Property details
- Listing history
- Listing removals
- Relists
- Price changes
- Sale/rent alternation
- Garage spaces
- Gas-service evidence
- Quiet Score
- Vibrancy Score
- APN when visible

### 4.3 Cross-check sources

Only after initial Redfin discovery, cross-check selected or high-interest properties against:

- Zillow
- Realtor.com
- Homes.com
- Compass
- County Recorder/Assessor

County records are used to verify sales and ownership-transfer resets.

## 5. Active Redfin search paths

### 5.1 Murrieta path with Temecula region parameter

```text
https://www.redfin.com/city/12866/CA/Murrieta/filter/property-type=house,min-price=550k,max-price=990k,min-beds=2,min-baths=2,min-parking=2,pool-type=no-private,mr=6:19701
```

### 5.2 Temecula path with Murrieta region parameter

```text
https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house,min-price=550k,max-price=990k,min-beds=2,min-baths=2,min-parking=2,pool-type=no-private,mr=6:12866
```

## 6. Core filters

### 6.1 Hard search filters from Redfin URL

- Property type: house
- Price: $550,000 to $990,000
- Minimum bedrooms: 2
- Minimum bathrooms: 2
- Minimum parking spaces: 2
- Private pool: no

### 6.2 Quiet/Vibrancy location preference

Quiet Score is the gatekeeper.

Recommended initial scoring:

- Reject or heavily downgrade if Quiet Score < 7.0
- Target if Quiet Score >= 8.0 and Vibrancy Score <= 2.5
- Excellent if Quiet Score >= 9.0 and Vibrancy Score <= 2.0

Low Vibrancy alone is not sufficient. The target is very high Quiet plus very low Vibrancy.

Quiet and Vibrancy are proxy indicators for avoiding major roads, freeways, airports, high-activity corridors, and other noise/activity sources.

### 6.3 Gas-service rule

Any mention of gas means the property has natural gas supply/service.

Examples:

- Gas fireplace
- Gas range
- Gas cooktop
- Gas oven
- Gas heating
- Gas dryer hookup
- Natural gas connected
- Gas utility
- Gas appliances

Normalize all to:

```text
gas_service = true
```

### 6.4 Walkability exclusion

Walkability-type information is not part of the initial project scope.

## 7. Human-in-the-loop workflow

MarketSentry must not automatically add every discovered home to the long-term watch database.

Workflow:

1. Discover candidates.
2. Save candidates to a review queue.
3. Export review queue to CSV or Excel.
4. User marks each candidate as Save, Reject, Maybe, or Needs More Review.
5. Only saved candidates move to the active watch database.
6. Watched properties are monitored over time.

## 8. MVP goals

### MVP 1: Project scaffold and database foundation

Create:

- Project folder structure
- SQLite database schema
- Configuration files
- CLI entry point
- Logging
- Initial tests

No scraping required yet.

### MVP 2: Candidate review queue import/export

Create the database tables and support manual seed data. Export candidate review queue to CSV. Import user decisions.

### MVP 3: Redfin candidate discovery

Given the two Redfin search URLs, collect candidate property URLs and summary fields where technically feasible and compliant.

### MVP 4: Redfin detail extraction

For each candidate URL, collect property details, listing history, garage spaces, gas-service evidence, Quiet/Vibrancy, and displayed DOM where available.

### MVP 5: Effective DOM engine

Convert listing history into metrics:

- displayed_dom
- current_listing_instance_dom
- sale_cycle_dom
- rent_sale_exposure_dom
- calendar_exposure_dom
- effective_dom
- effective_dom_delta
- listing_churn_count
- dom_reset_count
- sale_rent_alternation_count

### MVP 6: Scoring engine

Create initial scoring:

- location_fit_score
- quiet_gatekeeper_result
- property_fit_score
- effective_dom_leverage_score
- data_confidence_score

### MVP 7: Watchlist promotion

Import reviewed CSV/Excel and promote selected homes to watched_properties.

### MVP 8: Cross-site enrichment

For watched properties only, cross-check Zillow, Realtor.com, Homes.com, and Compass.

### MVP 9: County verification

For watched and high-interest properties, support Riverside County Assessor/Recorder verification.

### MVP 10: Monitoring

Track changes over time using observation snapshots and listing events.

## 9. Non-goals for initial version

- No automatic offer recommendations
- No seller-intent accusations
- No bypassing anti-bot protections
- No MLS/CRMLS integration until authorized access exists
- No walkability scoring
- No fully automated buying decisions
- No large-scale scraping before compliance review

## 10. Success criteria

### Technical success

- Local Python project runs from CLI.
- SQLite database is created reliably.
- Candidate review queue works.
- Manual review import/export works.
- Effective DOM calculations are tested.
- Scoring functions are deterministic and unit-tested.
- User-selected properties can be watched.

### Analytical success

- The system identifies properties with high displayed-DOM vs Effective-DOM divergence.
- The system rejects or downgrades noisy locations even when Vibrancy is low.
- The system captures gas-service evidence consistently.
- The system preserves source URLs and timestamps for auditability.
- The system keeps user review in control.

## 11. Required Claude Code completion feedback

After each implementation step, Claude Code must report:

1. Files created or modified.
2. Commands run.
3. Test results.
4. Any dependency changes.
5. Any unresolved questions.
6. Any assumptions made.
7. Any source-access limitations encountered.
8. Recommended next implementation step.
9. Git commit hash after successful commit and push to origin/main.

Claude must not mark a step complete until tests pass and changes are committed and pushed to origin/main.
