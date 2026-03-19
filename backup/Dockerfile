FROM --platform=linux/amd64 postgres:14-alpine
RUN apk update && apk add python3
COPY entrypoint.sh /srv/
COPY health_daemon.py /srv/
ENTRYPOINT ["/srv/entrypoint.sh"]
