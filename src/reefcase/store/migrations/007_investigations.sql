-- 007: agent investigation reports per survey (architecture §4.2, §5.5, §6.4).

CREATE TABLE IF NOT EXISTS investigations (
    id VARCHAR PRIMARY KEY,
    survey_id VARCHAR NOT NULL,
    findings VARCHAR NOT NULL,         -- JSON array of Finding
    hypotheses VARCHAR NOT NULL,       -- JSON array of Hypothesis
    verdict VARCHAR NOT NULL,
    actions VARCHAR NOT NULL,          -- JSON array of strings
    uncertain_frames VARCHAR NOT NULL, -- JSON array of frame IDs
    model VARCHAR NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS investigations_survey_idx ON investigations (survey_id);
