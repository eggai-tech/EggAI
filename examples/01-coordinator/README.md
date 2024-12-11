
# Getting Started with `EggAI Multi-Agent Framework`

This guide will help you quickly set up and get started with the EggAI Multi-Agent Framework.

## Prerequisites

- Python 3.10+
- Docker and Docker Compose

---

## Setup

### 1. Create a Virtual Environment (Optional)

To keep dependencies isolated, create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

Install the `eggai` library:

```bash
pip install eggai
```

### 3. Start Docker Containers

Use Docker Compose to start the required services in detached mode:

```bash
docker compose up -d
```

---

## Running the Application

Execute the `main.py` file:

```bash
python main.py
```

---

## Stopping Services

Stop and clean up the Docker containers:

```bash
docker compose down -v
```

---

You're now ready to explore EggAI Multi-Agent Framework! 🚀
