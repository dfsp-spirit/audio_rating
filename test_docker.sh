#!/bin/sh
#
# Run all docker-based tests that correspond to the root test_*.sh scripts.
# Assumes docker-compose.dev.yml stack is already running.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

./test_docker_backend_unit.sh
./test_docker_backend_integration.sh

echo "Skipping E2E by default for speed. Run './test_docker_e2e.sh' to include browser tests."
