# AutoRecruit Ops

Recruitment agentic workflow app for resume extraction, job-opening curation and candidate-to-job matching. The stack uses React, FastAPI, Redis, Celery, CrewAI, Phoenix, Qdrant, and local `uploads/` plus `workspace/` storage.

The runtime path is:

```text
React UI -> FastAPI routes -> Redis queue -> Celery/background worker -> ai execution -> workspace artifacts
```

## Repository Layout

```text
Makefile
docker-compose.yml
.env.example
README.md
AGENTS.md
data/                         # sample resumes and UI sample manifest
uploads/                      # uploaded source files, runtime only
workspace/                    # generated candidate/job/match/run artifacts
src/
├── backend/                  # FastAPI app, Celery worker, services, tests
├── ai/                       # CrewAI crews, pipelines, prompts, tracing
├── shared/                   # Pydantic schemas
└── frontend/                 # React/Vite UI
```

## Source Map

### Backend: `src/backend`

- `app/main.py`: FastAPI app assembly and route registration.
- `app/api/routes/`: HTTP and SSE endpoints.
  - `cv.py`: resume upload/extraction tasks and resume progress stream.
  - `recruitment.py`: job-opening curation, job records, and job progress stream.
  - `orchestration.py`: candidate analysis, stored-candidate matching, and match progress stream.
  - `cv_matching.py`: direct CV matching endpoint.
  - `workspace.py`: safe reads for generated workspace artifacts.
  - `settings.py`, `samples.py`, `health.py`: supporting endpoints.
- `app/services/`: file parsing, uploads, workspace IO, Redis progress events, Celery enqueueing, PII redaction, Qdrant, and sample data.
- `app/workers/`: Celery app and task definitions.
- `tests/`: backend pytest tests.

### AI: `src/ai`

- `pipelines/cv_extraction_flow.py`: resume parse, validation, structured extraction, missing-field review, markdown curation, persistence.
- `pipelines/job_opening_flow.py`: job text/URL ingestion, validation, structured extraction, missing-field review, markdown curation, persistence.
- `pipelines/cv_matching_flow.py`: matching context, parallel match analyses, overall synthesis, final response assembly, run logging.
- `pipelines/candidate_analysis_flow.py`: uploaded-resume extraction plus matching orchestration.
- `crews/`: CrewAI agents and tasks for extraction and matching.
- `prompts/`: prompt builders and prompt text.
- `events/`: CrewAI event listener and runtime context for SSE progress, guardrails, model names, token usage, and latency.
- `formatters/`: Markdown renderers.
- `providers/`: live model vs deterministic fallback selection.
- `runtime/`: CrewAI cost/latency run limits.
- `tracing/`: Phoenix setup, run logs, token/cost stats.

### Shared: `src/shared`

- `schemas/cv.py`: resume extraction schemas.
- `schemas/job_opening.py`: job-opening schemas.
- `schemas/matching.py`: matching request/response schemas.
- `schemas/orchestration.py`: candidate analysis response schemas.
- `crewai_limits.py`: AI runtime-limits.

### Frontend: `src/frontend`

- `src/App.jsx`: dashboard, candidates, job openings, matching, settings, progress trackers, artifact preview, and match result UI.
- `src/styles.css`: Tailwind component classes.
- `src/main.jsx`: React entrypoint.

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

`make setup` copies `.env.example` to `.env` if needed, validates required API keys, and builds Docker images. Set these in `.env` or your shell before setup:

- `OPENAI_API_KEY`
- `SERPER_API_KEY`

Python services use `uv` for dependency management inside containers.

## Run

```bash
make run
```

Main UI flows:

- Candidates: upload resumes, track extraction, preview generated Markdown and JSON.
- Job Openings: curate job postings from pasted text or URLs.
- Matching: match stored candidates or uploaded resumes against stored job openings.
- Dashboard: inspect run health, totals, and recent generated records.
- Settings: adjust AI run limits.

Generated runtime files are written into:

- `uploads/resumes/<candidate_id>/`
- `workspace/candidates/<candidate_id>/`
- `workspace/job_openings/<job_id>/`
- `workspace/runs/<run_id>/`
- `workspace/matches/`

See [workspace/README.md](workspace/README.md) and [workspace/AGENTS.md](workspace/AGENTS.md) for artifact navigation rules.

## Test

```bash
make test
```

Focused local checks:

```bash
cd src/backend && uv run pytest tests/test_cv_flow.py
cd src/backend && uv run pytest tests/test_cv_matching.py
cd src/backend && uv run pytest tests/test_orchestration_runs_api.py
cd src/frontend && npm run build
```

## Notes

- `OPENAI_MODEL` defaults to `gpt-4o-mini` and can be changed in `.env`.
- `PII_REDACTION_ENABLED` defaults to `true`. Parsed resume text exposed through API responses and trace artifacts is redacted before leaving the flow, while original parsed text is used internally for extraction.
- `PII_REDACTION_ENTITIES` defaults to `EMAIL_ADDRESS,PHONE_NUMBER,URL`.
- Phoenix tracing is initialized through OpenTelemetry and mirrored into workspace trace/log files for inspection.
- CrewAI and custom flow spans are exported to the Phoenix project configured by `PHOENIX_PROJECT_NAME`.
