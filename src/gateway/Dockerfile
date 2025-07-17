FROM python:3.10-slim

WORKDIR /app

COPY gateway_distribuido.py .
COPY config.ini .

EXPOSE 65432

CMD ["python", "gateway_distribuido.py"]