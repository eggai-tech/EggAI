FROM python:3.9

WORKDIR /app

# Install mlflow and packages required to interact with PostgreSQL and MinIO
RUN pip install mlflow psycopg2 boto3 requests && \
    apt-get update && \
    apt-get install -y curl