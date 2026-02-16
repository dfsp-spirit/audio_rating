#!/bin/bash
#
# Run this script to start nginx with the development configuration that serves both the frontend and backend.
# Also runs the FastAPI backend on port 8000. Make sure to have nginx installed.
#
# To use this script, simply run it from the terminal. It will start nginx in the background and then run the FastAPI backend in the foreground.
# However, you need to properly configure the frontend and backend paths in the audiorating settings files to match the nginx configuration:
#
# - In the frontend, in file frontend/settings/ar_settings.js, set the API_BASE_URL to http://localhost/ar_backend/api
# - In the backend, in file backend/.env, make sure to:
#        * set the AR_ROOTPATH to /ar_backend
#        * set the AR_FRONTEND_URL to http://localhost:3000/rate/
#        * make sure that AR_ALLOWED_ORIGINS to '["http://localhost:3000", "http://127.0.0.1:3000"]', the default.
#
# You can access the frontend at http://localhost:3000/rate/ and the backend API at http://localhost:3000/ar_backend/api.


## Start nginx with the development configuration in background
NGINX_CONF="$HOME/develop_mpiae/audio_rating/backend/dev/dev.nginx.conf"

if [ ! -f "$NGINX_CONF" ]; then
    echo -e "${RED}❌ nginx configuration file not found at $NGINX_CONF${NC}"
    exit 1
fi

nginx -c "$NGINX_CONF"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Frontend available at http://localhost:3000/rate/${NC}"
else
    echo -e "${RED}❌ Failed to start nginx${NC}"
    exit 1
fi


## Start the FastAPI backend in the foreground (you can stop it with Ctrl+C)

cd backend/ && uv run uvicorn audiorating_backend.api:app --reload --host 127.0.0.1 --port 8000
