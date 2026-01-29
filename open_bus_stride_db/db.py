import os
from typing import ContextManager
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


SQLALCHEMY_APPLICATION_NAME = os.getenv("SQLALCHEMY_APPLICATION_NAME", "db")
SQLALCHEMY_APPLICATION_VERSION = os.getenv("SQLALCHEMY_APPLICATION_VERSION", "-")

_create_engine_kwargs = dict(
    future=True,
    connect_args={
        "options": "-c timezone=utc",
        "application_name": f'{SQLALCHEMY_APPLICATION_NAME} {SQLALCHEMY_APPLICATION_VERSION}'[:64],
    },
    echo=bool(os.environ.get('SQLALCHEMY_ECHO')),
)
if os.getenv("SQLALCHEMY_POOLCLASS_NULLPOOL") == "yes":
    from sqlalchemy.pool import NullPool
    _create_engine_kwargs.update(
        poolclass=NullPool,
        pool_pre_ping=True,
    )
else:
    _create_engine_kwargs.update(
        dict(
            pool_size=int(os.environ.get('SQLALCHEMY_POOL_SIZE', 10)),
            max_overflow=int(os.environ.get('SQLALCHEMY_MAX_OVERFLOW', 20)),
            pool_timeout=int(os.environ.get('SQLALCHEMY_POOL_TIMEOUT', 30)),
        )
    )

engine = create_engine(
    os.environ.get('SQLALCHEMY_URL', 'postgresql://postgres:123456@localhost'),
    **_create_engine_kwargs,
)
_sessionmaker = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)


@contextmanager
def get_session(session=None) -> ContextManager[Session]:
    if session:
        # this supports a use-case for functions to work with or without an existing session
        yield session
    else:
        session: Session = _sessionmaker()
        try:
            yield session
        finally:
            session.close()


def session_decorator(func):

    def _func(*args, **kwargs):
        with get_session() as session:
            return func(session, *args, **kwargs)

    return _func
