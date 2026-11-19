"""Every app metric, defined once. Other modules import these and record values."""

from prometheus_client import Counter, Gauge, Histogram

DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Time to run one SQL statement.",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
)

DB_POOL_CHECKED_OUT = Gauge(
    "db_pool_checked_out", "DB connections in use by this pod right now."
)

DB_POOL_MAX_CONNECTIONS = Gauge(
    "db_pool_max_connections",
    "Most DB connections this pod can open (pool size + overflow).",
)

# Labels stay a small fixed set: never a release id or a version string.
RELEASE_TRANSITIONS = Counter(
    "release_transitions_total",
    "Edit, publish and archive attempts by outcome.",
    ["action", "result"],
)

READINESS_FAILURES = Counter(
    "readiness_check_failures_total", "Readiness checks that could not reach the DB."
)

# Always 1; the version label shows which build this pod runs.
BUILD_INFO = Gauge("app_build_info", "Running app version.", ["version"])

LOCK_WAIT = Histogram(
    "release_lock_wait_seconds",
    "Time to take the row lock on a release.",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5),
)
