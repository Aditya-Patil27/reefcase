-- 002: replay index for the event log (architecture §6.2). The events PK
-- already covers (survey_id, seq); this named index makes the access path
-- explicit for the SSE replay scans.
CREATE INDEX IF NOT EXISTS events_survey_seq_idx ON events (survey_id, seq);
