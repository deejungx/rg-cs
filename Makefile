setup:
	cp -n .env.example .env || true
	docker compose build
	@echo "Setup complete. If OPENAI_API_KEY is empty, the app will run in deterministic mock mode."

run:
	docker compose up
	@echo "Frontend: http://localhost:8080"
	@echo "Backend: http://localhost:8000"
	@echo "Phoenix: http://localhost:6006"

test:
	docker compose run --rm backend uv run pytest

eval-deepeval:
	docker compose run --rm -e RUN_DEEPEVAL_EVALS=1 backend uv run deepeval test run tests/test_resume_validation_deepeval.py
