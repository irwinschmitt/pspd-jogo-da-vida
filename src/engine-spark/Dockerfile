FROM bitnami/spark:3.5.1

USER root

COPY main.py /app/main.py


RUN chown -R 1001:0 /app

USER 1001
