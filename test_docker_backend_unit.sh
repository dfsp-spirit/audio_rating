#!/bin/sh
#
# Run backend unit tests in Docker container.
# Assumes docker-compose.dev.yml stack is already running.

set -e

COMPOSE_FILE="docker-compose.dev.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Error: $COMPOSE_FILE not found"
    exit 1
fi

echo "Running backend unit tests in Docker"
echo "IMPORTANT: Make sure the docker dev stack is running via 'docker compose -f docker-compose.dev.yml up -d --build'"

docker compose -f "$COMPOSE_FILE" exec backend uv run pytest tests/unit -v --tb=short
