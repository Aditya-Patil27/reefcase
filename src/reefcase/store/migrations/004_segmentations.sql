-- 004: one segmentation mask per frame (architecture §4.2, §6.4).

CREATE TABLE IF NOT EXISTS segmentations (
    id VARCHAR PRIMARY KEY,
    frame_id VARCHAR NOT NULL,
    backend VARCHAR NOT NULL,
    mask_path VARCHAR NOT NULL,    -- palette PNG; pixel values are §4.2 class ids
    cover VARCHAR NOT NULL,        -- JSON object: SegClass value -> fraction
    latency_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS segmentations_frame_idx ON segmentations (frame_id);
