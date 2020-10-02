FROM python:buster

LABEL maintainer="simon@simonwakenhut.me"

RUN pip install requests pyyaml psycopg2

COPY ./src/openproject-sidecar.py /var/openproject/sidecar/openproject-sidecar.py
CMD python3 /var/openproject/sidecar/openproject-sidecar.py