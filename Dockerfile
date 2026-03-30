# Pulled Jun 13, 2023
FROM --platform=linux/amd64 python:3.8@sha256:1387025f39249bbee2ed49076e70be5da0715f9f7c6e167e07a1e84947d11ab6
RUN pip install --upgrade pip
RUN wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - &&\
    echo "deb http://apt.postgresql.org/pub/repos/apt/ bullseye-pgdg main" | tee  /etc/apt/sources.list.d/pgdg.list &&\
    apt-get update && apt-get install -y postgresql-client-14
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY setup.py ./
COPY open_bus_stride_db ./open_bus_stride_db
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install -e .
ENV PYTHONUNBUFFERED=1
COPY entrypoint.sh ./
ENTRYPOINT ["/srv/entrypoint.sh"]
