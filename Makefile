setup:
	cp -n .env.example .env || true
	docker compose build

run:
	docker compose up
	@echo "Frontend: http://localhost:8080"
	@echo "Backend: http://localhost:8000"
	@echo "Phoenix: http://localhost:6006"

test:
	docker compose run --rm backend uv run pytest
