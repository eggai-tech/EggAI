FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY agents /app/agents
COPY libraries /app/libraries

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

ENTRYPOINT ["python", "-m"]
