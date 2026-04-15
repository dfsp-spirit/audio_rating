#!/bin/sh
#
# Start the full Audiorating development stack in Docker.
# This mounts backend/frontend sources from disk for live development.

set -e

COMPOSE_FILE="docker-compose.dev.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Error: $COMPOSE_FILE not found"
    exit 1
fi

echo "Starting Docker development stack (db, backend, web)..."
echo "Frontend: http://localhost:3000/rate/study.html"
echo "Backend API: http://localhost:3000/ar_backend/api"
echo "Backend direct: http://localhost:8000/api"

docker compose -f "$COMPOSE_FILE" up --build
