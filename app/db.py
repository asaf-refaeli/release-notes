import time
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session

from app.config import get_settings
from app.metrics import (
    DB_POOL_CHECKED_OUT,
    DB_POOL_MAX_CONNECTIONS,
    DB_QUERY_DURATION,
)


# Time every SQL statement (SQLAlchemy FAQ recipe). Registered on the Engine class,
# so it covers every engine, including the one the tests use.
@event.listens_for(Engine, "before_cursor_execute")
def _start_query_timer(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start", []).append(time.perf_counter())


@event.listens_for(Engine, "after_cursor_execute")
def _stop_query_timer(conn, cursor, statement, parameters, context, executemany):
    started = conn.info["query_start"].pop()
    DB_QUERY_DURATION.observe(time.perf_counter() - started)


# A failed statement skips after_cursor_execute. Record it here, so slow failures
# (timeouts, lock errors) are still counted and no start time is left behind.
@event.listens_for(Engine, "handle_error")
def _stop_query_timer_on_error(context):
    starts = context.connection.info.get("query_start") if context.connection else None
    if starts:
        DB_QUERY_DURATION.observe(time.perf_counter() - starts.pop())


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    engine = create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        connect_args={"connect_timeout": 2},
    )
    # Called at each scrape. A lambda reads engine.pool fresh each time, because
    # engine.dispose() replaces the pool object.
    DB_POOL_CHECKED_OUT.set_function(lambda: engine.pool.checkedout())
    DB_POOL_MAX_CONNECTIONS.set(settings.db_pool_size + settings.db_max_overflow)
    return engine


EngineDep = Annotated[Engine, Depends(get_engine)]


def get_session(engine: EngineDep) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
