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
] + CREATE_INDEXES
