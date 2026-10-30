-- 006: one vision-model assessment per frame (architecture §4.2, §5.3).

CREATE TABLE IF NOT EXISTS assessments (
    id VARCHAR PRIMARY KEY,
    frame_id VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    bleaching_severity INTEGER NOT NULL,   -- 0..4
    morphology VARCHAR NOT NULL,           -- JSON array of strings
    damage VARCHAR NOT NULL,               -- JSON array of damage labels
    notes VARCHAR NOT NULL
);

CREATE INDEX IF NOT EXISTS assessments_frame_idx ON assessments (frame_id);
