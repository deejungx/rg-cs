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
- Load a shipped sample CV and JD, or upload your own CV
- Run the orchestration flow
- Inspect the structured result, model mode, and step-by-step trace

Included sample data:

- `data/good/happy_path_fullstack_resume.txt`: happy-path text resume
- `data/bad/edge_case_ambiguous_resume.txt`: ambiguous edge-case resume
- `data/samples.json`: manifest the frontend uses for one-click sample selection

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

## DeepEval

DeepEval is integrated at the CrewAI layer. Every CrewAI kickoff in the CV extraction pipeline is instrumented through `instrument_crewai()`, and the project uses DeepEval's `Crew`, `Agent`, and `LLM` shims so eval spans can be attached without rewriting the crews.

To run the opt-in resume-validation eval:

```bash
cd src/backend
RUN_DEEPEVAL_EVALS=1 uv run deepeval test run tests/test_resume_validation_deepeval.py
```

Or from the repo root:

```bash
make eval-deepeval
```

## Notes

- `MODEL_PROVIDER` defaults to `auto`. With a valid `OPENAI_API_KEY`, the app uses OpenAI. Without a key, it falls back to deterministic mock mode so the app still runs end to end on a clean machine.
- Set `OPENAI_API_KEY` in `.env` to enable CrewAI plus OpenAI inference for extraction and matching. If the key is empty, the UI and orchestration response explicitly show mock mode.
- `OPENAI_MODEL` defaults to `gpt-4o-mini` and can be changed in `.env`.
- `DEEPEVAL_ENABLED` defaults to `true`. Set it to `false` to disable DeepEval CrewAI instrumentation while keeping the rest of the pipeline unchanged.
- `PII_REDACTION_ENABLED` defaults to `true`. Parsed resume text exposed through API responses and trace artifacts is redacted with Presidio before it leaves the flow, while the original parsed text is still used internally for CV extraction.
- `PII_REDACTION_ENTITIES` defaults to `EMAIL_ADDRESS,PHONE_NUMBER,URL`, which keeps redaction deterministic and lightweight without requiring an external NLP model.
- The CV extraction workflow is implemented as a CrewAI `Flow` in [src/ai/pipelines/cv_extraction_flow.py](/home/deejung/rg-cs/src/ai/pipelines/cv_extraction_flow.py), with shared schema definitions in [src/shared/schemas/cv.py](/home/deejung/rg-cs/src/shared/schemas/cv.py).
- The browser-facing orchestration endpoint is implemented in [src/ai/pipelines/candidate_analysis_flow.py](/home/deejung/rg-cs/src/ai/pipelines/candidate_analysis_flow.py) and [src/backend/app/api/routes/orchestration.py](/home/deejung/rg-cs/src/backend/app/api/routes/orchestration.py).
- Parsing is handled by `pypdf` and `python-docx` in [src/backend/app/services/file_parser.py](/home/deejung/rg-cs/src/backend/app/services/file_parser.py).
- Text-based sample resumes (`.txt` and `.md`) are also supported for offline demo flows.
- Phoenix tracing is initialized through OpenTelemetry and also mirrored into workspace trace files for easy inspection.
- CrewAI and custom Flow spans are exported to the Phoenix project configured by `PHOENIX_PROJECT_NAME` (`default` unless overridden). The local collector endpoint is configured by `PHOENIX_COLLECTOR_ENDPOINT`.
