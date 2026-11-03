"""SQLAlchemy sessions for the externally managed ClickHouse database."""

import os
from contextlib import contextmanager
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker


def create_clickhouse_engine():
    endpoint = urlparse(os.getenv("CLICKHOUSE_URL", "http://localhost:18123"))
    if endpoint.scheme not in ("http", "https") or not endpoint.hostname:
        raise ValueError("CLICKHOUSE_URL must be an HTTP or HTTPS URL")
    url = URL.create(
        "clickhouse+http",
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        host=endpoint.hostname,
        port=endpoint.port or (443 if endpoint.scheme == "https" else 80),
        database=os.getenv("CLICKHOUSE_DATABASE", "default"),
        query={"protocol": endpoint.scheme},
    )
    return create_engine(url)


@contextmanager
def get_session():
    """Open a ClickHouse ORM session and release its engine on exit."""
    engine = create_clickhouse_engine()
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
