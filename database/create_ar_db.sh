#!/bin/bash
#
# Script to set up PostgreSQL database and user based on .env file.
#
# This script will create the database and database user, but the postgresql server must be
# running and accessible.
# Note that it does NOT create any tables or relations in the database. The backend application
# will create the required tables automatically when it is started for the first time.
#
# This is a development setup script and is not intended for production use. It assumes that:
#  1) you are developing on your local machine, and not using Docker
#  2) you have sudo access to the postgres user
#  3) the database server is running on the same machine
#  4) peer authentication is enabled in postgres for local connections
#
# Usage: in the repo root, as a user with sudo access to the postgres system user, run:
#
#    ./database/create_tud_db.sh .env
#

echo "=== Database setup for TUD backend ==="
echo " This script creates the database and database user with password as specified in the .env file."
echo " It requires sudo access to the 'postgres' user on a local PostgreSQL server."
echo "Note that the TUD_DATABASE_USER and TUD_DATABASE_PASSWORD read from the .env file are the ones that will be created by this script,"
echo "not the superuser credentials that will be used by this script to connect to the postgres server."
echo ""


# Default .env location
DEFAULT_ENV_PATH=".env"

# Allow custom .env path
ENV_PATH="${1:-$DEFAULT_ENV_PATH}"

if [ ! -f "$ENV_PATH" ]; then
    echo "ERROR: .env file not found at path: '$ENV_PATH'"
    echo "Please create it first or specify a custom path:"
    echo "  ./create_tud_db.sh /path/to/your/.env"
    exit 1
fi

echo "Loading configuration from env file: '$ENV_PATH'"
source "$ENV_PATH"


source ".env"   # Loads environment variables DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD

TUD_DATABASE_HOST=${TUD_DATABASE_HOST:-localhost}
TUD_DATABASE_PORT=${TUD_DATABASE_PORT:-5432}

# After sourcing the .env file, validate required variables
if [ -z "$TUD_DATABASE_NAME" ] || [ -z "$TUD_DATABASE_USER" ] || [ -z "$TUD_DATABASE_PASSWORD" ]; then
    echo "ERROR: Missing required database configuration in '.env' file."
    echo "Please ensure TUD_DATABASE_NAME, TUD_DATABASE_USER, and TUD_DATABASE_PASSWORD are set."
    echo "Note that the TUD_DATABASE_USER and TUD_DATABASE_PASSWORD are the ones that will be created by this script,"
    echo "not the superuser credentials that will be used by this script to connect to the postgres server."
    exit 1
fi

echo "Loaded env vars from '.env' file and defaults:"
echo " TUD_DATABASE_HOST='$TUD_DATABASE_HOST'"
echo " TUD_DATABASE_PORT='$TUD_DATABASE_PORT'"
echo " TUD_DATABASE_NAME='$TUD_DATABASE_NAME'"
echo " TUD_DATABASE_USER='$TUD_DATABASE_USER'"
## End of env file handling

# Define SQL commands once
SQL_COMMANDS=$(cat << SQL_EOF
CREATE DATABASE ${TUD_DATABASE_NAME};
-- Revoke all default privileges from PUBLIC in this database
REVOKE ALL ON DATABASE ${TUD_DATABASE_NAME} FROM PUBLIC;

CREATE USER ${TUD_DATABASE_USER} WITH
    PASSWORD '${TUD_DATABASE_PASSWORD}'
    NOCREATEDB
    NOCREATEROLE
    NOSUPERUSER
    NOREPLICATION;

GRANT CONNECT ON DATABASE ${TUD_DATABASE_NAME} TO ${TUD_DATABASE_USER};
\c ${TUD_DATABASE_NAME}

-- Lock down the public schema completely
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO ${TUD_DATABASE_USER};

-- Your app privileges (these are perfect)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${TUD_DATABASE_USER};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${TUD_DATABASE_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${TUD_DATABASE_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${TUD_DATABASE_USER};
SQL_EOF
)

echo "Setting up PostgreSQL database '${TUD_DATABASE_NAME}' and new user '${TUD_DATABASE_USER}' as specified in the .env file..."

if [ "$TUD_DATABASE_HOST" = "localhost" ] || [ "$TUD_DATABASE_HOST" = "127.0.0.1" ]; then
    echo "Using peer auth as system user postgres for local database server at host '$TUD_DATABASE_HOST'..."
    sudo -u postgres psql << EOF
    $SQL_COMMANDS
EOF
else
    echo "ERROR: Remote database hosts are not supported by this setup script."
    exit 1
fi

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to set up database or user. Please check the error messages above."
    exit 1
fi

echo "Database setup complete. Check for errors above."