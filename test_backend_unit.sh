#!/bin/sh
#
# Finish dev installation before running this. There is no need to run services for the unit tests.

echo "Running backend unit tests"


if [ ! -d "backend/tests/unit" ]; then
    echo "Error: This script must be run from the root directory of the project."
    exit 1
fi

cd backend && uv run pytest tests/unit