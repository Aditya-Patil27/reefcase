-- 005: every tool result, cached by (tool, canonical JSON params) (§5.4, §6.4).
-- ``params_key`` is the cache half the SQL can index; ``params``/``data`` stay JSON text.

CREATE TABLE IF NOT EXISTS tool_results (
    id VARCHAR PRIMARY KEY,
    tool VARCHAR NOT NULL,
    params_key VARCHAR NOT NULL,   -- canonical JSON of params (the cache key half)
    params VARCHAR NOT NULL,       -- JSON object, as validated
    data VARCHAR NOT NULL,         -- JSON object the tool returned
    source_url VARCHAR NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS tool_results_cache_idx ON tool_results (tool, params_key);
