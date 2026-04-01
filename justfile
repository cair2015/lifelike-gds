set dotenv-load := true

default:
  @just --list

# Bootstrap the project environment
setup:
  uv sync

# Add a runtime dependency:
# just add requests
add pkg:
  uv add {{pkg}}

# Add a dev dependency:
# just add-dev pytest
add-dev pkg:
  uv add --dev {{pkg}}

# Run the app
# run:
#   uv run python main.py

# Run tests
test:
  uv run pytest

# Lint
lint:
  uv run ruff check .

# Format
format:
  uv run ruff format .

# Fix what can be fixed automatically
fix:
  uv run ruff check . --fix
  uv run ruff format .

# Type-check, if you use mypy
typecheck:
  uv run mypy .

# Update lockfile / environment explicitly
sync:
  uv sync

lock:
  uv lock

# Show dependency tree
deps:
  uv tree

# Clean local caches / env
clean:
  rm -rf .venv
  find . -type d -name "__pycache__" -prune -exec rm -rf {} +
  find . -type f -name "*.pyc" -delete