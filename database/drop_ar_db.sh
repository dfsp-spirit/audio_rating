#!/bin/bash
#
# Drop (delete) the PostgreSQL database used by the AR backend web app.
#
# This is a development setup script and is not intended for production use. It assumes that:
#  1) you are developing on your local machine, and not using Docker
#  2) you have sudo access to the postgres user
#  3) the database server is running on the same machine
#  4) peer authentication is enabled in postgres for local connections
#
# Usage: in the repo root, as a user with sudo access to the postgres system user, run:
#
#    ./database/drop_ar_db.sh .env
#

echo "=== Drop database of the AR backend web app, deleting all user data ==="
echo "NOTE: This script is for development use only. It is not intended for production use."
echo "Note that the AR_DATABASE_NAME and AR_DATABASE_USER read from the .env file are the ones that will be dropped by this script,"
echo "not the superuser credentials that will be used by this script to connect to the postgres server."
echo ""


# Default .env location
DEFAULT_ENV_PATH=".env"

# Allow custom .env path
ENV_PATH="${1:-$DEFAULT_ENV_PATH}"

if [ ! -f "$ENV_PATH" ]; then
    echo "ERROR: .env file not found at path: '$ENV_PATH'"
    echo "Please create it first or specify a custom path:"
    echo "  ./create_ar_db.sh /path/to/your/.env"
    exit 1
fi

echo "Loading configuration from env file: '$ENV_PATH'"
source "$ENV_PATH"


AR_DATABASE_HOST=${AR_DATABASE_HOST:-localhost}
AR_DATABASE_PORT=${AR_DATABASE_PORT:-5432}

# After sourcing the .env file, validate required variables
if [ -z "$AR_DATABASE_NAME" ] || [ -z "$AR_DATABASE_USER" ]; then
    echo "ERROR: Missing required database configuration in '.env' file."
    echo "Please ensure AR_DATABASE_NAME and AR_DATABASE_USER are set."
    exit 1
fi

echo "Loaded env vars from '.env' file or defaults:"
echo " AR_DATABASE_HOST='$AR_DATABASE_HOST'"
echo " AR_DATABASE_PORT='$AR_DATABASE_PORT'"
echo " AR_DATABASE_NAME='$AR_DATABASE_NAME'"
echo " AR_DATABASE_USER='$AR_DATABASE_USER'"
## End of env file handling

if [ "$AR_DATABASE_HOST" = "localhost" ] || [ "$AR_DATABASE_HOST" = "127.0.0.1" ]; then
    echo "Dropping database on localhost..."
else
    echo "ERROR: Remote database hosts are not supported by this drop database script."
    exit 1
fi

echo "WARNING: This will permanently delete the postgresql database '$AR_DATABASE_NAME' on localhost and all its data!"
read -p "Are you sure you want to continue? (y/N): " confirm

if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "Operation cancelled."
    exit 0
fi

echo "Dropping database '$AR_DATABASE_NAME'..."
sudo -u postgres psql << EOF
DROP DATABASE IF EXISTS $AR_DATABASE_NAME;
DROP USER IF EXISTS $AR_DATABASE_USER;
\echo "Database '$AR_DATABASE_NAME' dropped successfully"
\echo "User '$AR_DATABASE_USER' dropped successfully"
EOF

echo "Database drop complete!"