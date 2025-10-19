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
- `static/script.js` – Submits code to `/analyze` and `/analyze_repo`, renders structured results with severity badges and repo UI

### UI usage for GitHub repos

- Paste a public GitHub URL in the textbox (supports branches and subdirectories like `.../tree/<branch>/<path>`), then click "Review Code".
- A "Repository Summary" section appears with:
  - repo, branch, subdirectory
  - top-level tree and extension counts
  - a clickable file list. Click any `REVIEWED` file to load its Security, Maintainability, and Style into the tabs.
- The "All Files" tab shows an aggregate table with per-file issue counts and quick "View" links.
- Use "Download Report" to export a unified Markdown report for the entire repository.

## API endpoints

- `GET /health` → `{ "status": "ok" }`
- `GET /health_config` → Diagnostic JSON of provider/base_url/model/api_key presence
- `POST /analyze` → JSON response:
  - Success: `{ status: "success", analysis_results: {...}, feedback: "..." }`
  - Error: `{ status: "error", error: "...", analysis_results: {} }`
 - `POST /analyze_repo` → Analyze a public GitHub repository URL. Body: `{ repo_url, include_extensions?, max_files? }`
 - `POST /analyze_repo_report` → Returns a Markdown attachment `code_review_report.md` for a repo URL. Body: `{ repo_url, include_extensions?, max_files? }`

## Internals and workflow

- `src/agent.py` builds a LangGraph with nodes:
  - `ingest_code` → validates inputs and sets metadata
  - `run_analyses` → runs security, maintainability, and style in parallel, merges results
  - `synthesize_feedback` → creates a comprehensive, formatted summary
  - `handle_error` → returns structured error message
- Conditional edge added:
  - From `ingest_code` → `handle_error` when state contains `error`, else → `run_analyses`
- The Flask route bridges async calls with `asyncio.run`.

### Repository analysis internals

- `src/repo_analyzer.py`:
  - Parses GitHub URLs (owner/repo/branch/subdir), downloads ZIP via `codeload.github.com`, extracts to a temp dir.
  - Summarizes structure (tree + extension counts), filters files by extensions (`.py`, `.ipynb` by default), enforces max files.
  - Reads `.ipynb` code cells, sends each selected file through `CodeReviewAgent` sequentially.
  - Returns a unified JSON with per-file results; `build_markdown_report()` converts it into a human-readable report.

## Troubleshooting

- 500 on `/analyze`:
  - Check `.env` contains a valid API key.
  - Verify packages: `python -c "import pydantic, pydantic_settings; print(pydantic.__version__)"` (should print v2.x).
- Pydantic errors:
  - Ensure `pydantic>=2` and `pydantic-settings>=2` are installed.
- "Node handle_error is not reachable":
  - Confirm `src/agent.py` includes the conditional edge from `ingest_code`.

- 401 from provider (e.g., "User not found"):
  - Use a consistent provider + base URL + key.
    - OpenRouter: set `OPENROUTER_API_KEY`, `OPENAI_BASE_URL=https://openrouter.ai/api/v1`, `OPENAI_MODEL=mistralai/mistral-7b-instruct`.
    - OpenAI: set `OPENAI_API_KEY`, `OPENAI_BASE_URL=https://api.openai.com/v1`, `OPENAI_MODEL=gpt-4o-mini` (or your model).
  - Do not set both keys at the same time. Restart the server after changing `.env`.
  - Visit `GET /health_config` to verify runtime config.

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

### Analyze a GitHub repository (UI)

1) Paste a public GitHub URL into the textbox and click "Review Code".
2) Click any `REVIEWED` file in the list to load its 3 categories.
3) Open the "All Files" tab to view aggregate counts and jump to files.
4) Click "Download Report" to save `code_review_report.md`.

### Analyze a GitHub repository (API)

```bash
curl -X POST http://localhost:8000/analyze_repo \
  -H 'Content-Type: application/json' \
  -d '{
    "repo_url": "https://github.com/owner/repo/tree/main/subdir",
    "include_extensions": [".py", ".ipynb"],
    "max_files": 20
  }'
```

Download Markdown report:

```bash
curl -X POST http://localhost:8000/analyze_repo_report \
  -H 'Content-Type: application/json' \
  -d '{ "repo_url": "https://github.com/owner/repo" }' \
  -o code_review_report.md
```

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
  - `repo_analyzer.py` - GitHub repo downloader, extractor, structure summarizer, per-file reviews, Markdown report builder
  - `cli.py` - Command-line interface
  - `config.py` - Configuration settings
- `tests/` - Unit tests (coming soon)
- `requirements.txt` - Python dependencies
- `templates/` - Flask templates
  - `index.html` - Main UI with repo and per-file views
- `static/` - Static assets
  - `style.css` - Styling
  - `script.js` - UI logic (form submit, repo analysis, aggregate table, per-file view, report download)

### Adding Support for New Languages

1. Add the file extension to `SUPPORTED_LANGUAGES` in `src/config.py`
2. The agent will automatically try to analyze any file type, but results may vary

## License

MIT
