# Triage Agent Dataset Generator and Manager

A toolkit for generating, managing, and editing datasets for the EggAI Triage Agent.

## Features

- Generate synthetic datasets for triage agent training
- Store datasets in a PostgreSQL database
- View and manage datasets through a web interface
- Edit individual examples in datasets
- Filter and search through examples

## Tech Stack

- **Backend**: FastAPI
- **Frontend**: HTML, Tailwind CSS (via CDN), Alpine.js
- **Database**: PostgreSQL
- **Containerization**: Docker, Docker Compose
- **LLM Integration**: LiteLLM

## Project Structure

The project uses a modern src-layout:

```
triage-toolkit/
├── src/
│   ├── triage_agent_dataset/    # Dataset generation package
│   │   ├── __init__.py
│   │   ├── __main__.py          # CLI entry point
│   │   ├── models.py            # Data models
│   │   ├── config.py            # Configuration
│   │   ├── constants.py         # Constants
│   │   └── dataset_generator.py # Generator logic
│   │
│   └── triage_webserver/        # Web server package
│       ├── __init__.py
│       ├── __main__.py          # CLI entry point
│       ├── app.py               # FastAPI application
│       ├── config.py            # Server configuration
│       ├── database/            # Database connections
│       ├── models/              # SQLAlchemy models
│       ├── routes/              # API endpoints
│       ├── schemas/             # Pydantic models
│       ├── services/            # Business logic
│       ├── static/              # Static assets
│       └── templates/           # HTML templates
│
├── pyproject.toml               # Project metadata and dependencies
├── docker-compose.yml           # Docker Compose configuration
└── Dockerfile                   # Docker configuration
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- API key for your preferred LLM provider (OpenAI, Anthropic, or Gemini)

### Installation and Setup

1. Clone the repository:
   ```
   git clone [repository-url]
   cd triage-agent-dataset
   ```

2. Create a `.env` file from the example:
   ```
   cp .env.example .env
   ```

3. Edit the `.env` file and add your LLM API key(s):
   ```
   OPENAI_API_KEY=your-openai-key-here
   # or
   ANTHROPIC_API_KEY=your-anthropic-key-here
   # or
   GEMINI_API_KEY=your-gemini-key-here
   ```

4. Start the application with Make:
   ```
   make start
   ```

5. Access the web interface:
   ```
   http://localhost:8000
   ```

## Command Line Interface

The package provides two command-line tools:

### triage-generate

Generate datasets without the web interface:

```bash
# Basic usage
triage-generate

# Generate with custom parameters
triage-generate --output custom-dataset.jsonl --total 200 --temperatures 0.7 0.9 --turns 1 3 5 7
```

Options:
- `--output`, `-o`: Output file path (default: dataset.jsonl)
- `--temperatures`, `-t`: List of temperatures to use (default: 0.7 0.8 0.9)
- `--turns`, `-u`: List of turns to use (default: 1 3 5)
- `--total`, `-n`: Total number of examples to generate

### triage-server

Start the web server:

```bash
# Basic usage
triage-server

# With custom host and port
triage-server --host 127.0.0.1 --port 9000

# Development mode with auto-reload
triage-server --reload
```

Options:
- `--host`: Host to bind the server to (default: 0.0.0.0)
- `--port`: Port to bind the server to (default: 8000 or PORT env var)
- `--reload`: Enable auto-reload for development

## Development

### Local Development Setup

1. Create and activate a virtual environment:
   ```bash
   # Using the provided script
   ./install-dev.sh
   source .venv/bin/activate
   
   # Or manually
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

2. Start the server:
   ```bash
   triage-server --reload
   ```

3. Generate a dataset:
   ```bash
   triage-generate
   ```

### Using the Makefile

The repository includes a Makefile with common tasks:

```bash
# Setup development environment
make setup

# Start the application with Docker
make start

# View logs
make logs

# Stop services
make stop

# Rebuild and start
make rebuild

# Run web server without Docker
make run-web

# Run dataset generator without Docker
make run-gen

# Show all available commands
make help
```

For detailed help on each command, run `make help`.

For Windows users without Make, please see `WINDOWS_DEV.md` for detailed instructions.

### Development Scripts

The repository includes Python scripts to run the application directly:

- `dev_webserver.py` - Run the web server in development mode
- `dev_generator.py` - Run the dataset generator directly

## API Endpoints

The application provides a RESTful API:

- **GET /api/datasets**: List all datasets
- **POST /api/datasets**: Create a new dataset
- **GET /api/datasets/{id}**: Get a specific dataset
- **DELETE /api/datasets/{id}**: Delete a dataset
- **GET /api/examples**: List examples (filterable by dataset_id, target_agent, special_case)
- **GET /api/examples/{id}**: Get a specific example
- **PUT /api/examples/{id}**: Update an example
- **DELETE /api/examples/{id}**: Delete an example

## License

[License information]