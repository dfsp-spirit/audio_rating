#!/bin/sh
#
# Run frontend E2E tests in Docker (Playwright container).
# Assumes docker-compose.dev.yml stack is already running.

set -e

COMPOSE_FILE="docker-compose.dev.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Error: $COMPOSE_FILE not found"
    exit 1
fi

echo "Running frontend E2E tests in Docker"
echo "IMPORTANT: Make sure the docker dev stack is running via 'docker compose -f docker-compose.dev.yml up -d --build'"

docker compose --profile e2e -f "$COMPOSE_FILE" run --rm e2e
