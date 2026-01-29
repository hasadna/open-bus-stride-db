import os
import time
import importlib
import subprocess

from open_bus_stride_db import db as db_module

import pytest


@pytest.fixture(scope="session")
def get_db():
    create_container = True
    if os.getenv("KEEP_TEST_POSTGRES_CONTAINER") == "yes":
        if subprocess.call([
            "docker", "container", "inspect", "open-bus-stride-db-test-postgres"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            create_container = False
    if create_container:
        subprocess.call([
            "docker", "rm", "-f", "open-bus-stride-db-test-postgres"
        ])
        subprocess.check_call([
            "docker", "run", "--name", "open-bus-stride-db-test-postgres",
            "-e", "POSTGRES_USER=postgres",
            "-e", "POSTGRES_PASSWORD=123456",
            "-p", "5432:5432",
            "-d", "postgres:14"
        ])
        time.sleep(3)

    def get_db_(poolclass_nullpool=False):
        os.environ["SQLALCHEMY_URL"] = "postgresql://postgres:123456@localhost"
        if poolclass_nullpool:
            os.environ["SQLALCHEMY_POOLCLASS_NULLPOOL"] = "yes"
        elif "SQLALCHEMY_POOLCLASS_NULLPOOL" in os.environ:
            del os.environ["SQLALCHEMY_POOLCLASS_NULLPOOL"]
        importlib.reload(db_module)
        return db_module

    try:
        yield get_db_
    finally:
        if os.getenv("KEEP_TEST_POSTGRES_CONTAINER") != "yes":
            subprocess.call([
                "docker", "rm", "-f", "open-bus-stride-db-test-postgres"
            ])
