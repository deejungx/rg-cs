FROM python:3.12-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Install uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy the application into the container.
COPY ./agent-runtime /app

WORKDIR /app

# Install dependencies
RUN uv sync --locked --no-dev

# Run the worker
CMD ["uv", "run", "celery", "-A", "worker", "worker", "--loglevel=info", "-Q", "agent_tasks", "--concurrency=4"]
