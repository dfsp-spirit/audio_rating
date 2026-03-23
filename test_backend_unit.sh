#!/bin/sh
#
# Finish dev installation before running this, and have the backend running via './run_dev_nginx_both.bash' in another terminal before starting this...

echo "Running backend unit tests"
echo "IMPORTANT: Make sure the backend is running via './run_dev_nginx_both.bash' in another terminal before starting this..."

if [ ! -d "backend/tests/unit" ]; then
    echo "Error: This script must be run from the root directory of the project."
    exit 1
fi

cd backend && uv run pytest tests/unit