# Recruitment AI Scaffold

Docker Compose scaffold for a CV-processing AI workflow with a React frontend, FastAPI backend, Redis/Celery background jobs, Qdrant vector storage, Arize Phoenix tracing, and local `uploads/` plus `workspace/` runtime storage. The setup follows the same high-level pattern as the copied reference apps: frontend talks only to FastAPI, FastAPI enqueues Celery work, and the worker runs the AI orchestration separately.

## Repository Layout

```text
Makefile
docker-compose.yml
.env.example
README.md
uploads/
workspace/
src/
├── frontend/
├── backend/
├── ai/
└── shared/
```

## Services

- Frontend: http://localhost:8080
- Backend API: http://localhost:8000
- Phoenix UI: http://localhost:6006
- Qdrant API: http://localhost:6333
- Redis: `redis://localhost:6379`

## Setup

```bash
make setup
```

This copies `.env.example` to `.env` if needed and builds the Docker images. The Python services use `uv` for dependency management inside the containers.

## Run

```bash
make run
```

Main flows:

- Open the UI at http://localhost:8080
- Upload a CV
- Queue extraction
- Watch task status and inspect generated results and artifacts

Generated runtime files are written into:

- `uploads/resumes/<candidate_id>/`
- `workspace/candidates/<candidate_id>/`

## Test

```bash
make test
```

Included automated checks cover:

- backend health endpoint
- extraction enqueue endpoint
- Celery task registration
- CrewAI extraction flow artifact creation
- workspace file creation

## Notes

- Set `OPENAI_API_KEY` in `.env` to enable CrewAI plus OpenAI inference for CV extraction. If the key is empty, the worker falls back to deterministic scaffolded outputs so the app still works end to end.
- `OPENAI_MODEL` defaults to `gpt-4o-mini` and can be changed in `.env`.
- The CV extraction workflow is implemented as a CrewAI `Flow` in [src/ai/pipelines/cv_extraction_flow.py](/home/deejung/rg-cs/src/ai/pipelines/cv_extraction_flow.py), with shared schema definitions in [src/shared/schemas/cv.py](/home/deejung/rg-cs/src/shared/schemas/cv.py).
- Parsing is handled by `pypdf` and `python-docx` in [src/backend/app/services/file_parser.py](/home/deejung/rg-cs/src/backend/app/services/file_parser.py).
- Phoenix tracing is initialized through OpenTelemetry and also mirrored into workspace trace files for easy inspection.
- CrewAI and custom Flow spans are exported to the Phoenix project configured by `PHOENIX_PROJECT_NAME` (`default` unless overridden). The local collector endpoint is configured by `PHOENIX_COLLECTOR_ENDPOINT`.
