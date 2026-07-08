setup:
	cp -n .env.example .env || true
	@set -eu; \
	openai_key="$${OPENAI_API_KEY:-}"; \
	serper_key="$${SERPER_API_KEY:-}"; \
	if [ -z "$$openai_key" ]; then \
		openai_key=$$(grep -E '^OPENAI_API_KEY=' .env 2>/dev/null | tail -n 1 | cut -d '=' -f2- | tr -d '[:space:]' || true); \
	fi; \
	if [ -z "$$serper_key" ]; then \
		serper_key=$$(grep -E '^SERPER_API_KEY=' .env 2>/dev/null | tail -n 1 | cut -d '=' -f2- | tr -d '[:space:]' || true); \
	fi; \
	if [ -z "$$openai_key" ] || [ "$$openai_key" = "YOUR_API_KEY" ] || [ "$$openai_key" = "your_api_key" ] || [ "$$openai_key" = "changeme" ]; then \
		echo "ERROR: OPENAI_API_KEY must be set in your environment or in .env before running setup."; \
		exit 1; \
	fi; \
	if [ -z "$$serper_key" ] || [ "$$serper_key" = "YOUR_API_KEY" ] || [ "$$serper_key" = "your_api_key" ] || [ "$$serper_key" = "changeme" ]; then \
		echo "ERROR: SERPER_API_KEY must be set in your environment or in .env before running setup."; \
		exit 1; \
	fi; \
	docker compose build; \
	echo "Setup complete."

run:
	docker compose up
	@echo "Frontend: http://localhost:8080"
	@echo "Backend: http://localhost:8000"
	@echo "Phoenix: http://localhost:6006"

test:
	docker compose run --rm backend uv run pytest
