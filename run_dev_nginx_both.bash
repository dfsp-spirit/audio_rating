#!/bin/bash
#
# Run this script to start nginx with the development configuration that serves both the frontend and backend.
# Also runs the FastAPI backend on port 8000. Make sure to have nginx installed and configured to allow running as a non-root user if needed.


## Start nginx with the development configuration in background
NGINX_CONF="$HOME/develop_mpiae/audio_rating/backend/dev/dev.nginx.conf"

if [ ! -f "$NGINX_CONF" ]; then
    echo -e "${RED}❌ nginx configuration file not found at $NGINX_CONF${NC}"
    exit 1
fi

nginx -c "$NGINX_CONF"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Frontend available at http://localhost/rate/${NC}"
else
    echo -e "${RED}❌ Failed to start nginx${NC}"
    exit 1
fi


## Start the FastAPI backend in the foreground (you can stop it with Ctrl+C)

cd backend/ && uv run uvicorn audiorating_backend.api:app --reload --host 127.0.0.1 --port 8000
