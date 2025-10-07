# Agentic Code Reviewer (Flask UI)

An AI-powered code review agent that analyzes code for security, maintainability, and style using LangChain + LangGraph. This repo now uses a Flask-only web UI to display structured results.

## Features

- 🔍 Automatic code analysis for multiple programming languages
- 📝 Detailed feedback on code quality, security, and performance
- 🚀 Integration with OpenAI's language models for intelligent suggestions
- 🔄 Customizable review workflows using LangGraph
- 🛠️ Command-line interface for easy integration into your workflow

## What changed in this setup

- Removed Streamlit and FastAPI. The project now serves a single Flask app.
- Added structured UI (HTML/CSS/JS) under `templates/` and `static/` that renders the same detailed output you saw in the terminal.
- Fixed workflow so `handle_error` is reachable via conditional edges in `src/agent.py`.
- Fixed Flask backend to bridge async agent calls using `asyncio.run`.
- Consolidated dependencies for Python 3.12 compatibility.

## Requirements

- Python 3.12 (recommended)
- A working OpenRouter or OpenAI-compatible API key

## Create a Conda environment (Python 3.12)

```bash
conda create -n code-reviewer python=3.12 -y
conda activate code-reviewer
```

## Install dependencies

```bash
pip install -r requirements.txt
```

Key dependencies:
- `flask`, `jinja2` for the UI
- `langchain`, `langgraph`, `langchain-openai` for LLM orchestration
- `pydantic>=2` and `pydantic-settings>=2` for configuration
- optional: `ruff`, `bandit`, `radon`

## Environment variables

Create a `.env` in the project root with at least one of the following keys. The app maps `OPENROUTER_API_KEY` to `openai_api_key` automatically.

```
# Use one of the keys below
OPENAI_API_KEY=sk-...
# or
OPENROUTER_API_KEY=or-...

# Optional overrides
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=mistralai/mistral-7b-instruct
```

If no API key is found, `src/config.py` will raise:
`ValueError("API key is required. Set OPENAI_API_KEY or OPENROUTER_API_KEY in .env")`

## Run the Flask app

```bash
python flask_backend.py
```
Open http://localhost:8000

## UI structure

- `templates/index.html` – Main page with code input + tabs (Security, Maintainability, Style)
- `static/style.css` – Modern, responsive styling
- `static/script.js` – Submits code to `/analyze`, renders structured results with severity badges

## API endpoints

- `GET /health` → `{ "status": "ok" }`
- `POST /analyze` → JSON response:
  - Success: `{ status: "success", analysis_results: {...}, feedback: "..." }`
  - Error: `{ status: "error", error: "...", analysis_results: {} }`

## Internals and workflow

- `src/agent.py` builds a LangGraph with nodes:
  - `ingest_code` → validates inputs and sets metadata
  - `run_analyses` → runs security, maintainability, and style in parallel, merges results
  - `synthesize_feedback` → creates a comprehensive, formatted summary
  - `handle_error` → returns structured error message
- Conditional edge added:
  - From `ingest_code` → `handle_error` when state contains `error`, else → `run_analyses`
- The Flask route bridges async calls with `asyncio.run`.

## Troubleshooting

- 500 on `/analyze`:
  - Check `.env` contains a valid API key.
  - Verify packages: `python -c "import pydantic, pydantic_settings; print(pydantic.__version__)"` (should print v2.x).
- Pydantic errors:
  - Ensure `pydantic>=2` and `pydantic-settings>=2` are installed.
- "Node handle_error is not reachable":
  - Confirm `src/agent.py` includes the conditional edge from `ingest_code`.

## Summary of file changes

- `src/agent.py`:
  - Added conditional routing so `handle_error` is reachable.
  - Improved fallback synthesis formatting and response cleaning.
- `flask_backend.py`:
  - Replaced `await` with `asyncio.run(...)` in `/analyze`.
  - Added `/health` endpoint and better JSON error responses.
- `requirements.txt`:
  - Removed Streamlit and FastAPI deps, added Flask + Jinja2, pinned Pydantic v2 series.
- Removed files (no longer used):
  - `app.py` (Streamlit), `fastapi_backend.py`, `requirements_fastapi.txt`, `start_dashboard.*`, `README_WEB_DASHBOARD.md`
- UI files (kept):
  - `templates/index.html`, `static/style.css`, `static/script.js`

## Usage

### Review a Single File
```bash
python -m src.cli path/to/your/file.py
```

### Interactive Mode
```bash
python -m src.cli
```
Then enter the file path when prompted.

## Supported Languages

- Python
- JavaScript
- TypeScript
- Java
- Go

## Configuration

You can customize the behavior by modifying the `.env` file or directly in `src/config.py`.

## Development

### Project Structure

- `src/` - Main source code
  - `agent.py` - Core agent implementation
  - `cli.py` - Command-line interface
  - `config.py` - Configuration settings
- `tests/` - Unit tests (coming soon)
- `requirements.txt` - Python dependencies

### Adding Support for New Languages

1. Add the file extension to `SUPPORTED_LANGUAGES` in `src/config.py`
2. The agent will automatically try to analyze any file type, but results may vary

## License

MIT
