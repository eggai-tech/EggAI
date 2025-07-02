FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY agents /app/agents
COPY libraries /app/libraries
COPY scripts /app/scripts

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

USER 1000

ENTRYPOINT ["python", "-m"]
