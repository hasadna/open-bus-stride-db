import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


engine = create_engine(os.environ['SQLALCHEMY_URL'], future=True)
Session = sessionmaker(bind=engine, future=True)


def session_decorator(func):

    def _func(*args, **kwargs):
        with Session() as session:
            return func(session, *args, **kwargs)

    return _func
