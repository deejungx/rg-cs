# Repository Guidelines

## Project Structure & Module Organization
`src/backend` contains the FastAPI API, Celery worker code, and backend tests. Core app code lives in `src/backend/app`, while backend test files live in `src/backend/tests`.  
`src/ai` holds CrewAI flows, prompts, eval harnesses, tracing, and runtime helpers.  
`src/shared` contains shared schemas and limits used across backend and AI layers.  
`src/frontend` contains the frontend app. Runtime artifacts are written to `uploads/` and `workspace/`.

## Build, Test, and Development Commands
- `make setup`: copies `.env.example` to `.env` and builds Docker images.
- `make run`: starts the full stack with Docker Compose.
- `make test`: runs the backend pytest suite inside the backend container.
- `cd src/backend && uv run pytest tests/test_pii_redaction_service.py`: run a focused backend test locally.

## Coding Style & Naming Conventions
Use Python 3.12+ style with 4-space indentation and type hints on public functions. Prefer small service classes and explicit schema models over ad hoc dictionaries.  
Use `snake_case` for modules, functions, and variables; `PascalCase` for classes; and descriptive test names like `test_cv_flow_redacts_parsed_text_in_result_and_trace`.  
Keep comments sparse and practical. Follow the existing import grouping and keep configuration in `app/core/config.py`.

## Testing Guidelines
Backend tests use `pytest` and live under `src/backend/tests/test_*.py`. Add focused regression tests for any flow, parser, tracing, or redaction change.  
When adding eval logic, keep reusable eval datasets in `src/ai/evals` and keep pytest wrappers thin.  
Run targeted tests first, then `make test` for broader validation.

## Commit & Pull Request Guidelines
Current history is minimal (`init`, `wip`), so use short, imperative commit messages with clear scope, for example: `add presidio pii redaction`.  
PRs should include:
- a concise summary of behavior changes
- any config or dependency updates
- test coverage added or updated
- screenshots only for frontend-visible changes

## Security & Configuration Tips
Do not commit real secrets in `.env`. Keep PII protections enabled unless a task explicitly requires otherwise.  
For resume-processing changes, be explicit about whether data is raw, redacted, persisted, or only used in-memory.
