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

## save current directory to return to it later
CURRENT_DIR=$(pwd)

NGINX_CONF_DIR="./dev_tools/local_nginx/webserver_config/"

if [ ! -d "$NGINX_CONF_DIR" ]; then
    echo -e "❌ nginx configuration directory not found at $NGINX_CONF_DIR"
    exit 1
fi

cd "$NGINX_CONF_DIR" || { echo -e "❌ Failed to change directory to $NGINX_CONF_DIR"; exit 1; }



# Create the nginx configuration file from the template, replacing 'USERHOME' with the actual home directory
NGINX_CONF_FILE="./dev.nginx.conf"
./replace_home.sh dev.nginx.conf.template "$NGINX_CONF_FILE" || { echo -e "❌ Failed to create nginx configuration file from template"; exit 1; }


if [ ! -f "$NGINX_CONF_FILE" ]; then
    echo -e "❌ nginx configuration file not found at $NGINX_CONF_FILE in current working directory $(pwd)"
    exit 1
fi

FULL_NGINX_CONF_PATH="$(pwd)/$NGINX_CONF_FILE" # nginx requires an absolute path to the configuration file, or changing its config dir.

nginx -c "$FULL_NGINX_CONF_PATH"

if [ $? -eq 0 ]; then
    echo -e "✅ Started nginx successfully, frontend available at http://localhost:3000/rate/"
    echo -e "✅ Backend API available at http://localhost:3000/ar_backend/api"
    echo -e "INFO nginx is running in the background with configuration from $FULL_NGINX_CONF_PATH"
    echo -e "INFO Press CTRL+C to stop the FastAPI backend, and then run 'kill -QUIT \$(cat \$HOME/nginx-dev.pid)' to stop nginx"
else
    echo -e "❌ Failed to start nginx"
    exit 1
fi


## Start the FastAPI backend in the foreground (you can stop it with Ctrl+C)

cd "$CURRENT_DIR" && cd backend/ && uv run uvicorn audiorating_backend.api:app --reload --host 127.0.0.1 --port 8000 || { echo -e " Failed to start FastAPI backend"; exit 1; }


