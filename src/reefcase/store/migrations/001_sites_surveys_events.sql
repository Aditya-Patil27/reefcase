-- 001: sites, surveys and the event log (architecture §4.2, §4.3, §6.2, §6.4).
-- ``schema_migrations`` itself is created by ``store/db.py`` before any migration runs.

CREATE TABLE IF NOT EXISTS sites (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    lat DOUBLE NOT NULL,
    lon DOUBLE NOT NULL,
    mpa_id VARCHAR,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS surveys (
    id VARCHAR PRIMARY KEY,
    site_id VARCHAR NOT NULL,
    dive_date DATE NOT NULL,
    status VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    video_path VARCHAR,
    cover VARCHAR,              -- JSON object: class -> fraction (§4.2)
    failure_reason VARCHAR,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    survey_id VARCHAR NOT NULL,
    seq INTEGER NOT NULL,
    type VARCHAR NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    data VARCHAR NOT NULL,       -- JSON payload, the §4.3 fields minus survey_id/seq/ts/type
    PRIMARY KEY (survey_id, seq)
);
