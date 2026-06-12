"""ClickHouse table DDL — strings ONLY at Phase 1; execution lands in Phase 2.

Tables (CLAUDE.md build target):
  - events:          the typed event log — THE product. Append-only.
  - metrics:         replayed/live service metrics for the causal LAG/LEAD SQL.
  - airbyte_history: 90-day GitHub+Jira pull for the ownership baseline.
"""

EVENTS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS events (
    ts          DateTime64(3, 'UTC'),
    incident_id String,
    event_type  LowCardinality(String),
    payload     String
)
ENGINE = MergeTree
ORDER BY (incident_id, ts)
"""

METRICS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS metrics (
    ts      DateTime64(3, 'UTC'),
    service LowCardinality(String),
    metric  LowCardinality(String),
    value   Float64
)
ENGINE = MergeTree
ORDER BY (service, metric, ts)
"""

AIRBYTE_HISTORY_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS airbyte_history (
    ts          DateTime64(3, 'UTC'),
    source      LowCardinality(String),
    record_type LowCardinality(String),
    external_id String,
    author      String,
    title       String,
    payload     String
)
ENGINE = MergeTree
ORDER BY (source, record_type, ts)
"""

ALL_TABLE_DDL: dict[str, str] = {
    "events": EVENTS_TABLE_DDL,
    "metrics": METRICS_TABLE_DDL,
    "airbyte_history": AIRBYTE_HISTORY_TABLE_DDL,
}
