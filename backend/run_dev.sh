#!/bin/bash
#
# Run minimal local development environment with uvicorn exposed directly to the frontend (no nginx reverse proxy, no FastAPI rootpath).


# Copy the local nginx development .env file (backend settings file) that sets the proper settings, including empty FastAPI root path.
ENV_FILE_SOURCE="./dev_tools/local_minimal/backend_settings/.env.dev-minimal"

if [ ! -f "$ENV_FILE_SOURCE" ]; then
    echo -e "❌ .env file not found at $ENV_FILE_SOURCE"
    exit 1
fi

ENV_FILE_DESTINATION="./backend/.env"
cp "$ENV_FILE_SOURCE" "$ENV_FILE_DESTINATION" || { echo -e "❌ Failed to copy .env file from $ENV_FILE_SOURCE to $ENV_FILE_DESTINATION"; exit 1; }


uv run uvicorn audiorating_backend.api:app --reload --host 127.0.0.1 --port 8000
