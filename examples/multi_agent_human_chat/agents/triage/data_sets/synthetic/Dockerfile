FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
COPY uv.lock .

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy source code
COPY src/ /app/src/

# Install application in development mode
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Run the application
CMD ["triage-server", "--reload"]