#!/bin/bash
#
# Drop (delete) the PostgreSQL database used by the TUD backend web app.
#
# This is a development setup script and is not intended for production use. It assumes that:
#  1) you are developing on your local machine, and not using Docker
#  2) you have sudo access to the postgres user
#  3) the database server is running on the same machine
#  4) peer authentication is enabled in postgres for local connections
#
# Usage: in the repo root, as a user with sudo access to the postgres system user, run:
#
#    ./database/drop_tud_db.sh .env
#

echo "=== Drop database of the TUD backend web app, deleting all user data ==="
echo "NOTE: This script is for development use only. It is not intended for production use."
echo "Note that the TUD_DATABASE_NAME and TUD_DATABASE_USER read from the .env file are the ones that will be dropped by this script,"
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


TUD_DATABASE_HOST=${TUD_DATABASE_HOST:-localhost}
TUD_DATABASE_PORT=${TUD_DATABASE_PORT:-5432}

# After sourcing the .env file, validate required variables
if [ -z "$TUD_DATABASE_NAME" ] || [ -z "$TUD_DATABASE_USER" ]; then
    echo "ERROR: Missing required database configuration in '.env' file."
    echo "Please ensure TUD_DATABASE_NAME and TUD_DATABASE_USER are set."
    exit 1
fi

echo "Loaded env vars from '.env' file or defaults:"
echo " TUD_DATABASE_HOST='$TUD_DATABASE_HOST'"
echo " TUD_DATABASE_PORT='$TUD_DATABASE_PORT'"
echo " TUD_DATABASE_NAME='$TUD_DATABASE_NAME'"
echo " TUD_DATABASE_USER='$TUD_DATABASE_USER'"
## End of env file handling

if [ "$TUD_DATABASE_HOST" = "localhost" ] || [ "$TUD_DATABASE_HOST" = "127.0.0.1" ]; then
    echo "Dropping database on localhost..."
else
    echo "ERROR: Remote database hosts are not supported by this drop database script."
    exit 1
fi

echo "WARNING: This will permanently delete the postgresql database '$TUD_DATABASE_NAME' on localhost and all its data!"
read -p "Are you sure you want to continue? (y/N): " confirm

if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "Operation cancelled."
    exit 0
fi

echo "Dropping database '$TUD_DATABASE_NAME'..."

sudo -u postgres psql << EOF
DROP DATABASE IF EXISTS $TUD_DATABASE_NAME;
DROP USER IF EXISTS $TUD_DATABASE_USER;
\echo "Database '$TUD_DATABASE_NAME' dropped successfully"
\echo "User '$TUD_DATABASE_USER' dropped successfully"
EOF

echo "Database drop complete!"