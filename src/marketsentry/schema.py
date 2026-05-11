"""Database schema definitions."""

# SQL schema for SQLite database

CREATE_CANDIDATE_REVIEW_QUEUE_TABLE = """
CREATE TABLE IF NOT EXISTS candidate_review_queue (
    candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    discovery_date DATE NOT NULL,
    source_site TEXT NOT NULL,
    source_search_url TEXT NOT NULL,
    redfin_url TEXT NOT NULL,
    address TEXT NOT NULL,
    normalized_address TEXT,
    city TEXT NOT NULL,
    zip TEXT NOT NULL,
    price REAL,
    beds INTEGER,
    baths REAL,
    sqft INTEGER,
    lot_size REAL,
    displayed_dom INTEGER,
    quiet_score REAL,
    vibrancy_score REAL,
    quiet_gatekeeper_result TEXT,
    garage_spaces INTEGER,
    gas_service BOOLEAN,
    gas_evidence TEXT,
    effective_dom_estimate INTEGER,
    listing_churn_count INTEGER,
    dom_reset_count INTEGER,
    sale_rent_alternation_count INTEGER,
    review_status TEXT DEFAULT 'pending',
    user_decision TEXT,
    user_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_WATCHED_PROPERTIES_TABLE = """
CREATE TABLE IF NOT EXISTS watched_properties (
    property_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_saved_date DATE NOT NULL,
    active_watch_status BOOLEAN DEFAULT 1,
    redfin_url TEXT,
    zillow_url TEXT,
    realtor_url TEXT,
    homes_url TEXT,
    compass_url TEXT,
    address TEXT NOT NULL,
    normalized_address TEXT,
    city TEXT NOT NULL,
    zip TEXT NOT NULL,
    apn TEXT,
    current_price REAL,
    original_observed_price REAL,
    beds INTEGER,
    baths REAL,
    sqft INTEGER,
    lot_size REAL,
    garage_spaces INTEGER,
    gas_service BOOLEAN,
    gas_evidence TEXT,
    quiet_score REAL,
    vibrancy_score REAL,
    displayed_dom INTEGER,
    effective_dom INTEGER,
    effective_dom_delta INTEGER,
    listing_churn_count INTEGER,
    dom_reset_count INTEGER,
    sale_rent_alternation_count INTEGER,
    county_sale_verified BOOLEAN,
    ownership_transfer_found BOOLEAN,
    last_checked_date DATE,
    next_check_date DATE,
    watch_priority INTEGER,
    user_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_PROPERTY_OBSERVATION_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS property_observation_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    snapshot_date TIMESTAMP NOT NULL,
    source_site TEXT NOT NULL,
    listing_status TEXT,
    price REAL,
    displayed_dom INTEGER,
    effective_dom INTEGER,
    effective_dom_delta INTEGER,
    quiet_score REAL,
    vibrancy_score REAL,
    garage_spaces INTEGER,
    gas_service BOOLEAN,
    listing_churn_count INTEGER,
    dom_reset_count INTEGER,
    sale_rent_alternation_count INTEGER,
    cross_site_confidence_score REAL,
    price_discrepancy_flag BOOLEAN DEFAULT 0,
    status_discrepancy_flag BOOLEAN DEFAULT 0,
    dom_discrepancy_flag BOOLEAN DEFAULT 0,
    price_change_count INTEGER DEFAULT 0,
    listing_history_hash TEXT,
    property_detail_hash TEXT,
    raw_source_url TEXT,
    notes TEXT,
    FOREIGN KEY (property_id) REFERENCES watched_properties (property_id)
);
"""

CREATE_LISTING_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS listing_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    candidate_id INTEGER,
    event_date DATE NOT NULL,
    source_site TEXT NOT NULL,
    event_type TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    source_listing_id TEXT,
    mls_number TEXT,
    confidence TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (property_id) REFERENCES watched_properties (property_id),
    FOREIGN KEY (candidate_id) REFERENCES candidate_review_queue (candidate_id)
);
"""

CREATE_SOURCE_PAGES_TABLE = """
CREATE TABLE IF NOT EXISTS source_pages (
    source_page_id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    candidate_id INTEGER,
    source_site TEXT NOT NULL,
    source_url TEXT NOT NULL,
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    retrieval_method TEXT,
    content_hash TEXT,
    parser_version TEXT,
    parse_status TEXT,
    notes TEXT,
    FOREIGN KEY (property_id) REFERENCES watched_properties (property_id),
    FOREIGN KEY (candidate_id) REFERENCES candidate_review_queue (candidate_id)
);
"""

CREATE_USER_REVIEW_ACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS user_review_actions (
    review_action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    action_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_decision TEXT NOT NULL,
    user_notes TEXT,
    promoted_property_id INTEGER,
    FOREIGN KEY (candidate_id) REFERENCES candidate_review_queue (candidate_id),
    FOREIGN KEY (promoted_property_id) REFERENCES watched_properties (property_id)
);
"""

CREATE_CROSS_SITE_OBSERVATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS cross_site_observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER,
    property_id INTEGER,
    source_site TEXT NOT NULL,
    source_url TEXT NOT NULL,
    normalized_source_url TEXT,
    observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    match_method TEXT,
    address TEXT,
    normalized_address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    price REAL,
    beds INTEGER,
    baths REAL,
    sqft INTEGER,
    lot_size REAL,
    listing_status TEXT,
    displayed_dom INTEGER,
    garage_spaces INTEGER,
    gas_service BOOLEAN,
    gas_evidence TEXT,
    listing_agent TEXT,
    listing_broker TEXT,
    mls_number TEXT,
    source_mls TEXT,
    property_description TEXT,
    parse_status TEXT DEFAULT 'success',
    parse_warnings TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES candidate_review_queue (candidate_id),
    FOREIGN KEY (property_id) REFERENCES watched_properties (property_id)
);
"""

CREATE_COUNTY_RECORD_OBSERVATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS county_record_observations (
    county_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER,
    property_id INTEGER,
    source_type TEXT NOT NULL,
    county_name TEXT DEFAULT 'Riverside',
    source_url TEXT,
    record_date DATE,
    record_type TEXT NOT NULL,
    normalized_record_type TEXT,
    document_number TEXT,
    document_title TEXT,
    apn TEXT,
    normalized_apn TEXT,
    address TEXT,
    normalized_address TEXT,
    city TEXT,
    state TEXT DEFAULT 'CA',
    zip TEXT,
    grantor TEXT,
    grantee TEXT,
    sale_price REAL,
    transfer_tax REAL,
    assessed_value REAL,
    owner_name TEXT,
    permit_number TEXT,
    permit_type TEXT,
    permit_status TEXT,
    match_method TEXT,
    confidence TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES candidate_review_queue (candidate_id),
    FOREIGN KEY (property_id) REFERENCES watched_properties (property_id)
);
"""

# Migration statements for existing databases
MIGRATE_PROPERTY_OBSERVATION_SNAPSHOTS_V2 = [
    "ALTER TABLE property_observation_snapshots ADD COLUMN effective_dom_delta INTEGER;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN listing_churn_count INTEGER;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN dom_reset_count INTEGER;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN sale_rent_alternation_count INTEGER;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN cross_site_confidence_score REAL;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN price_discrepancy_flag BOOLEAN DEFAULT 0;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN status_discrepancy_flag BOOLEAN DEFAULT 0;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN dom_discrepancy_flag BOOLEAN DEFAULT 0;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN price_change_count INTEGER DEFAULT 0;",
]

# Milestone 10: Effective DOM v2 operational integration migrations
# These add v2 fields to property_observation_snapshots, watched_properties,
# and candidate_review_queue tables.

MIGRATE_SNAPSHOTS_V2_OPERATIONAL = [
    "ALTER TABLE property_observation_snapshots ADD COLUMN effective_dom_v1 INTEGER;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN effective_dom_v2 INTEGER;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN effective_dom_delta_v1 INTEGER;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN effective_dom_delta_v2 INTEGER;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN county_reset_applied BOOLEAN DEFAULT 0;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN county_reset_date DATE;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN county_reset_record_type TEXT;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN county_reset_confidence TEXT;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN recent_churn_index REAL;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN recent_churn_lookback_years INTEGER DEFAULT 3;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN recent_churn_event_count INTEGER;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN recent_dom_reset_count INTEGER;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN recent_sale_rent_alternation_count INTEGER;",
    "ALTER TABLE property_observation_snapshots ADD COLUMN churn_preserved_after_transfer BOOLEAN DEFAULT 1;",
]

MIGRATE_WATCHED_PROPERTIES_V2_OPERATIONAL = [
    "ALTER TABLE watched_properties ADD COLUMN effective_dom_v1 INTEGER;",
    "ALTER TABLE watched_properties ADD COLUMN effective_dom_v2 INTEGER;",
    "ALTER TABLE watched_properties ADD COLUMN effective_dom_delta_v1 INTEGER;",
    "ALTER TABLE watched_properties ADD COLUMN effective_dom_delta_v2 INTEGER;",
    "ALTER TABLE watched_properties ADD COLUMN county_reset_applied BOOLEAN DEFAULT 0;",
    "ALTER TABLE watched_properties ADD COLUMN county_reset_date DATE;",
    "ALTER TABLE watched_properties ADD COLUMN county_reset_record_type TEXT;",
    "ALTER TABLE watched_properties ADD COLUMN county_reset_confidence TEXT;",
    "ALTER TABLE watched_properties ADD COLUMN recent_churn_index REAL;",
    "ALTER TABLE watched_properties ADD COLUMN recent_churn_lookback_years INTEGER DEFAULT 3;",
    "ALTER TABLE watched_properties ADD COLUMN recent_churn_event_count INTEGER;",
    "ALTER TABLE watched_properties ADD COLUMN recent_dom_reset_count INTEGER;",
    "ALTER TABLE watched_properties ADD COLUMN recent_sale_rent_alternation_count INTEGER;",
    "ALTER TABLE watched_properties ADD COLUMN churn_preserved_after_transfer BOOLEAN DEFAULT 1;",
]

MIGRATE_CANDIDATE_REVIEW_QUEUE_V2_OPERATIONAL = [
    "ALTER TABLE candidate_review_queue ADD COLUMN effective_dom_v1 INTEGER;",
    "ALTER TABLE candidate_review_queue ADD COLUMN effective_dom_v2 INTEGER;",
    "ALTER TABLE candidate_review_queue ADD COLUMN effective_dom_delta_v1 INTEGER;",
    "ALTER TABLE candidate_review_queue ADD COLUMN effective_dom_delta_v2 INTEGER;",
    "ALTER TABLE candidate_review_queue ADD COLUMN county_reset_applied BOOLEAN DEFAULT 0;",
    "ALTER TABLE candidate_review_queue ADD COLUMN county_reset_date DATE;",
    "ALTER TABLE candidate_review_queue ADD COLUMN county_reset_record_type TEXT;",
    "ALTER TABLE candidate_review_queue ADD COLUMN county_reset_confidence TEXT;",
    "ALTER TABLE candidate_review_queue ADD COLUMN recent_churn_index REAL;",
    "ALTER TABLE candidate_review_queue ADD COLUMN recent_churn_lookback_years INTEGER DEFAULT 3;",
    "ALTER TABLE candidate_review_queue ADD COLUMN recent_churn_event_count INTEGER;",
    "ALTER TABLE candidate_review_queue ADD COLUMN recent_dom_reset_count INTEGER;",
    "ALTER TABLE candidate_review_queue ADD COLUMN recent_sale_rent_alternation_count INTEGER;",
    "ALTER TABLE candidate_review_queue ADD COLUMN churn_preserved_after_transfer BOOLEAN DEFAULT 1;",
]

# All v2 operational migration groups
ALL_V2_OPERATIONAL_MIGRATIONS = {
    "property_observation_snapshots": MIGRATE_SNAPSHOTS_V2_OPERATIONAL,
    "watched_properties": MIGRATE_WATCHED_PROPERTIES_V2_OPERATIONAL,
    "candidate_review_queue": MIGRATE_CANDIDATE_REVIEW_QUEUE_V2_OPERATIONAL,
}

# Milestone 25: Cross-site analytics trend snapshots table
CREATE_CROSS_SITE_ANALYTICS_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS cross_site_analytics_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    candidate_id INTEGER,
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    overall_cross_site_confidence_score REAL,
    discrepancy_severity_score REAL,
    discrepancy_severity_label TEXT,
    cross_site_manual_review_priority TEXT,
    weighted_price_agreement_score REAL,
    weighted_status_agreement_score REAL,
    weighted_dom_agreement_score REAL,
    weighted_garage_agreement_score REAL,
    weighted_gas_agreement_score REAL,
    source_freshness_score REAL,
    source_completeness_score REAL,
    source_agreement_score REAL,
    contributing_sources TEXT,
    low_confidence_sources TEXT,
    stale_sources TEXT,
    parse_warning_sources TEXT,
    source_count INTEGER DEFAULT 0,
    high_confidence_source_count INTEGER DEFAULT 0,
    low_confidence_source_count INTEGER DEFAULT 0,
    stale_source_count INTEGER DEFAULT 0,
    price_discrepancy_flag BOOLEAN DEFAULT 0,
    status_discrepancy_flag BOOLEAN DEFAULT 0,
    dom_discrepancy_flag BOOLEAN DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (property_id) REFERENCES watched_properties (property_id)
);
"""

# Milestone 26: Cross-site trend alerts table
CREATE_CROSS_SITE_TREND_ALERTS_TABLE = """
CREATE TABLE IF NOT EXISTS cross_site_trend_alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    candidate_id INTEGER,
    snapshot_id INTEGER,
    previous_snapshot_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    alert_status TEXT NOT NULL DEFAULT 'open',
    trend_direction TEXT,
    current_value TEXT,
    previous_value TEXT,
    delta_value TEXT,
    message TEXT,
    recommended_action TEXT,
    source_context TEXT,
    notes TEXT,
    FOREIGN KEY (property_id) REFERENCES watched_properties (property_id),
    FOREIGN KEY (snapshot_id) REFERENCES cross_site_analytics_snapshots (snapshot_id),
    FOREIGN KEY (previous_snapshot_id) REFERENCES cross_site_analytics_snapshots (snapshot_id)
);
"""

# Milestone 28: Cross-site alert triage actions table
CREATE_CROSS_SITE_ALERT_TRIAGE_ACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS cross_site_alert_triage_actions (
    triage_action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    triage_export_id TEXT NOT NULL,
    alert_id INTEGER NOT NULL,
    property_id INTEGER,
    action TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT,
    triage_notes TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alert_id) REFERENCES cross_site_trend_alerts (alert_id)
);
"""

# Index definitions for performance
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_candidates_review_status ON candidate_review_queue(review_status);",
    "CREATE INDEX IF NOT EXISTS idx_candidates_discovery_date ON candidate_review_queue(discovery_date);",
    "CREATE INDEX IF NOT EXISTS idx_candidates_normalized_address ON candidate_review_queue(normalized_address);",
    "CREATE INDEX IF NOT EXISTS idx_watched_active ON watched_properties(active_watch_status);",
    "CREATE INDEX IF NOT EXISTS idx_watched_normalized_address ON watched_properties(normalized_address);",
    "CREATE INDEX IF NOT EXISTS idx_watched_next_check ON watched_properties(next_check_date);",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_property ON property_observation_snapshots(property_id);",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_date ON property_observation_snapshots(snapshot_date);",
    "CREATE INDEX IF NOT EXISTS idx_events_property ON listing_events(property_id);",
    "CREATE INDEX IF NOT EXISTS idx_events_candidate ON listing_events(candidate_id);",
    "CREATE INDEX IF NOT EXISTS idx_events_date ON listing_events(event_date);",
    "CREATE INDEX IF NOT EXISTS idx_events_type ON listing_events(event_type);",
    "CREATE INDEX IF NOT EXISTS idx_cross_site_property ON cross_site_observations(property_id);",
    "CREATE INDEX IF NOT EXISTS idx_cross_site_candidate ON cross_site_observations(candidate_id);",
    "CREATE INDEX IF NOT EXISTS idx_cross_site_source ON cross_site_observations(source_site);",
    "CREATE INDEX IF NOT EXISTS idx_cross_site_observed_at ON cross_site_observations(observed_at);",
    "CREATE INDEX IF NOT EXISTS idx_county_property ON county_record_observations(property_id);",
    "CREATE INDEX IF NOT EXISTS idx_county_candidate ON county_record_observations(candidate_id);",
    "CREATE INDEX IF NOT EXISTS idx_county_normalized_apn ON county_record_observations(normalized_apn);",
    "CREATE INDEX IF NOT EXISTS idx_county_normalized_address ON county_record_observations(normalized_address);",
    "CREATE INDEX IF NOT EXISTS idx_county_record_date ON county_record_observations(record_date);",
    "CREATE INDEX IF NOT EXISTS idx_county_normalized_record_type ON county_record_observations(normalized_record_type);",
    "CREATE INDEX IF NOT EXISTS idx_county_document_number ON county_record_observations(document_number);",
    # Milestone 25: Cross-site analytics snapshots indexes
    "CREATE INDEX IF NOT EXISTS idx_cs_analytics_snapshots_property ON cross_site_analytics_snapshots(property_id);",
    "CREATE INDEX IF NOT EXISTS idx_cs_analytics_snapshots_captured ON cross_site_analytics_snapshots(captured_at);",
    # Milestone 26: Cross-site trend alerts indexes
    "CREATE INDEX IF NOT EXISTS idx_cs_trend_alerts_property ON cross_site_trend_alerts(property_id);",
    "CREATE INDEX IF NOT EXISTS idx_cs_trend_alerts_status ON cross_site_trend_alerts(alert_status);",
    "CREATE INDEX IF NOT EXISTS idx_cs_trend_alerts_severity ON cross_site_trend_alerts(severity);",
    "CREATE INDEX IF NOT EXISTS idx_cs_trend_alerts_type ON cross_site_trend_alerts(alert_type);",
    "CREATE INDEX IF NOT EXISTS idx_cs_trend_alerts_created ON cross_site_trend_alerts(created_at);",
    # Milestone 28: Cross-site alert triage actions indexes
    "CREATE INDEX IF NOT EXISTS idx_cs_triage_actions_export ON cross_site_alert_triage_actions(triage_export_id);",
    "CREATE INDEX IF NOT EXISTS idx_cs_triage_actions_alert ON cross_site_alert_triage_actions(alert_id);",
    "CREATE INDEX IF NOT EXISTS idx_cs_triage_actions_applied ON cross_site_alert_triage_actions(applied_at);",
]

# All schema statements in order
ALL_SCHEMA_STATEMENTS = [
    CREATE_CANDIDATE_REVIEW_QUEUE_TABLE,
    CREATE_WATCHED_PROPERTIES_TABLE,
    CREATE_PROPERTY_OBSERVATION_SNAPSHOTS_TABLE,
    CREATE_LISTING_EVENTS_TABLE,
    CREATE_SOURCE_PAGES_TABLE,
    CREATE_USER_REVIEW_ACTIONS_TABLE,
    CREATE_CROSS_SITE_OBSERVATIONS_TABLE,
    CREATE_COUNTY_RECORD_OBSERVATIONS_TABLE,
    CREATE_CROSS_SITE_ANALYTICS_SNAPSHOTS_TABLE,
    CREATE_CROSS_SITE_TREND_ALERTS_TABLE,
    CREATE_CROSS_SITE_ALERT_TRIAGE_ACTIONS_TABLE,
] + CREATE_INDEXES
