#!/bin/bash
#
# Run minimal frontend dev server basedon Python's http.server module

# Copy the proper frontend settings file that sets the proper API base URL for the nginx configuration.
FRONTEND_SETTINGS_SOURCE="./dev_tools/local_minimal/frontend_settings/ar_settings.dev-minimal.js"

if [ ! -f "$FRONTEND_SETTINGS_SOURCE" ]; then
    echo -e "❌ Frontend settings file not found at '$FRONTEND_SETTINGS_SOURCE'. Please make sure the file exists and try again."
    exit 1
fi

FRONTEND_SETTINGS_DESTINATION="./frontend/settings/ar_settings.js"
cp "$FRONTEND_SETTINGS_SOURCE" "$FRONTEND_SETTINGS_DESTINATION" || { echo -e "❌ Failed to copy frontend settings file from '$FRONTEND_SETTINGS_SOURCE' to '$FRONTEND_SETTINGS_DESTINATION'."; exit 1; }

echo "Connect to http://localhost:3000 now, e.g., run 'firefox http://localhost:3000/study.html &'"

cd frontend && python3 -m http.server 3000
