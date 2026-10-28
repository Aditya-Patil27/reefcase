-- 003: frames extracted from survey clips (architecture §4.2, §6.4).

CREATE TABLE IF NOT EXISTS frames (
    id VARCHAR PRIMARY KEY,
    survey_id VARCHAR NOT NULL,
    t_sec DOUBLE NOT NULL,
    image_path VARCHAR NOT NULL,
    quality VARCHAR NOT NULL       -- JSON object: blur, color_cast, turbidity, passed, reason (§4.2)
);

CREATE INDEX IF NOT EXISTS frames_survey_idx ON frames (survey_id, t_sec);
