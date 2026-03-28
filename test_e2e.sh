#!/bin/sh
#
# Finish dev installation before running this, and have sll services running via './run_dev_nginx_both.bash' in another terminal before starting this...
#
#
# To install tets dependencies, run the following command from the root directory of the project:
#
#  cd frontend/
#  npm install
#  npx npx playwright install --with-deps chromium
#

echo "Running E2E tests"
echo "IMPORTANT: Make sure all services are running via './run_dev_nginx_both.bash' in another terminal before starting this..."

if [ ! -d "frontend/tests/e2e" ]; then
    echo "Error: This script must be run from the root directory of the project."
    exit 1
fi

# You could also run a single test headed or 10 times with commands like:
#
# cd frontend/ && npx playwright test tests/e2e/study_page.spec.js --headed --project=chromium
# cd frontend/ && npx playwright test tests/e2e/study_page.spec.js --repeat-each=10
# cd frontend && npm run test:e2e -- --repeat-each=10

cd frontend && npm run test:e2e
