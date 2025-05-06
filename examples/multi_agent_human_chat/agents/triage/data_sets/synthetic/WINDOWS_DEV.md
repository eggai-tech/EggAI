# Windows Development Instructions

This document provides instructions for setting up and running the triage-toolkit on Windows when you don't have access to the `make` command.

## Setup

1. Create a virtual environment:
   ```
   python -m venv .venv
   ```

2. Activate the virtual environment:
   ```
   .venv\Scripts\activate
   ```

3. Install the package in development mode:
   ```
   pip install -e .
   ```

4. Install development dependencies:
   ```
   pip install -e ".[dev]"
   ```

5. Create a local environment file:
   ```
   copy .env.example .env
   ```

6. Edit the `.env` file to add your LLM API key (at least one is required).

## Alternatives to Make Commands

If you don't have Make installed on Windows, here are the equivalent commands:

| Make Command | Windows Equivalent |
|--------------|-------------------|
| `make setup` | Use steps 1-4 above |
| `make start` | `docker-compose up -d` |
| `make stop` | `docker-compose down` |
| `make logs` | `docker-compose logs -f` |
| `make db` | `docker-compose up -d db` |
| `make rebuild` | `docker-compose up -d --build` |
| `make run-web` | `python dev_webserver.py` |
| `make run-gen` | `python dev_generator.py` |

You can also install Make for Windows using [Chocolatey](https://chocolatey.org/) or [Scoop](https://scoop.sh/).

## Running the Application

### Running the Web Server

You can run the web server using the development script:

```
python dev_webserver.py
```

Or with custom host and port:

```
python dev_webserver.py --host 127.0.0.1 --port 9000
```

### Running the Dataset Generator

You can generate a dataset using the development script:

```
python dev_generator.py
```

With custom parameters:

```
python dev_generator.py --output my_dataset.jsonl --total 200
```

## Using Docker

If you have Docker Desktop for Windows installed, you can use Docker Compose:

```
docker-compose up -d
```

## Database Access

To connect to the PostgreSQL database, you can use the following connection details if running with Docker:

- Host: localhost
- Port: 5432
- Username: postgres
- Password: postgres
- Database: triage_db

You can use tools like pgAdmin or DBeaver to connect to the database.

## Troubleshooting

### Import Errors

If you get import errors, make sure your Python path includes the project root directory. The dev scripts handle this automatically.

### Port Already in Use

If port 8000 is already in use, you can specify a different port:

```
python dev_webserver.py --port 8080
```

### Database Connection Issues

If you can't connect to the database, make sure Docker is running and the database container is up:

```
docker-compose ps
```