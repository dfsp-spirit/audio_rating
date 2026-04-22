# audio_rating

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19595116.svg)](https://doi.org/10.5281/zenodo.19595116)
[![Backend Unit Tests](https://github.com/dfsp-spirit/audio_rating/actions/workflows/backend_unit_tests.yml/badge.svg)](https://github.com/dfsp-spirit/audio_rating/actions/workflows/backend_unit_tests.yml)
[![Backend Integration Tests](https://github.com/dfsp-spirit/audio_rating/actions/workflows/backend_integration_tests.yml/badge.svg)](https://github.com/dfsp-spirit/audio_rating/actions/workflows/backend_integration_tests.yml)
[![Frontend E2E Tests](https://github.com/dfsp-spirit/audio_rating/actions/workflows/e2e_tests.yml/badge.svg)](https://github.com/dfsp-spirit/audio_rating/actions/workflows/e2e_tests.yml)

Audiorating (AR) is a web application for music aesthetics research. It lets participants listen to audio, navigate the waveform, and assign ratings over time across multiple dimensions (for example valence, arousal, and enjoyment).

![Vis](./audio_rating_demo.gif?raw=true "Audio rating")

## About

Audiorating consists of three parts:

1. Frontend: a plain JavaScript app (no build required for normal development).
2. Backend: a FastAPI service with REST API and admin interface.
3. Database: PostgreSQL for participant and study data.

The frontend uses [wavesurfer.js](https://wavesurfer.xyz/) for waveform visualization and playback interaction.

## Features

- Supports common audio formats that work in modern browsers via Wavesurfer.
- Interactive waveform navigation and section-based rating.
- Multiple concurrent rating dimensions and scales.
- Study-driven configuration for songs, dimensions, and participant rules.
- Backend API for data collection and an admin interface for export and management.
- CSV export and automation-friendly admin API endpoints.

## Online Live Demo

You can try audio_rating live on GitHub pages:

- https://dfsp-spirit.github.io/audio_rating/study.html

## Installation Instructions

Audiorating consists of three components that are set up together:

1. PostgreSQL database
2. Python/FastAPI backend
3. Static frontend files

### Prerequisites

- PostgreSQL (recent version)
- Python 3.11+ and [`uv`](https://github.com/astral-sh/uv)
- Any web server that can serve static files and optionally proxy backend requests

### 1) Database Setup

Create a dedicated PostgreSQL database and user for Audiorating.

The backend creates required tables automatically on startup, as long as the database connection is configured correctly.

### 2) Backend Configuration

Copy the example environment file and adapt values for your setup:

```bash
cp backend/.env.example backend/.env
```

At minimum, configure:

- Database connection values (`AR_DATABASE_*` / `AR_DATABASE_URL`)
- Admin credentials (`AR_API_ADMIN_USERNAME`, `AR_API_ADMIN_PASSWORD`)
- Frontend URL and root path (`AR_FRONTEND_URL`, `AR_ROOTPATH`) depending on deployment path

Then install backend dependencies:

```bash
cd backend
uv sync --dev
```

### 3) Study Setup

Studies are defined in `backend/studies_config.json`.

On startup, the backend imports studies that do not exist yet. Existing studies are not overwritten automatically.

### 4) Frontend Configuration

Frontend runtime settings are defined in `frontend/src/settings/ar_settings.js`.

The most important value is `API_BASE_URL`, which must point to your backend API endpoint as seen from the browser.

No frontend build step is required for normal deployment.

### 5) Web Server Setup

Serve `frontend/src/` as static files with your preferred web server.

If frontend and backend share a domain, you can route backend requests through a sub-path (for example `/ar_backend/`) and set `AR_ROOTPATH` accordingly.

### 6) Admin Interface

The backend includes an admin interface for participant/study management and data export.

Access is protected with HTTP Basic Auth using the configured admin credentials.

### 7) Security Notes

For production deployments:

- Use HTTPS
- Use strong, unique passwords
- Restrict `AR_ALLOWED_ORIGINS` to the actual frontend origins
- Protect admin access and credentials

## Development

This project supports two local development workflows:

1. Local development without Docker (host-installed dependencies)
2. Local development with Docker Compose (containerized dev setup)

Both workflows use the same URL layout that mirrors production-style routing:

- Frontend: `http://localhost:3000/rate/study.html`
- Backend API (via nginx): `http://localhost:3000/ar_backend/api`
- Backend admin (via nginx): `http://localhost:3000/ar_backend/admin`

### Local Development Without Docker

Use this when you want maximum local control and the fastest edit/run loop on your host, or if you cannot or do not want to use Docker.

#### Prerequisites

- `git`
- `uv` (for Python environment and dependency management)
- `postgresql`
- `nginx`
- `node` and `npm` only if you run frontend E2E tests

Example setup on Ubuntu:

```bash
sudo apt install nginx git postgresql
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 1) Clone and initialize

```bash
git clone https://github.com/dfsp-spirit/audio_rating
cd audio_rating
```

#### 2) Configure local development settings

Copy nginx-based dev settings for backend and frontend:

```bash
cp dev_tools/local_nginx/backend_settings/.env.dev-nginx backend/.env
cp dev_tools/local_nginx/frontend_settings/ar_settings.dev-nginx.js frontend/src/settings/ar_settings.js
```

#### 3) Create the PostgreSQL database

```bash
./database/create_ar_db.sh backend/.env
```

#### 4) Install backend dependencies and run unit tests

```bash
cd backend
uv sync --dev
uv run pytest tests/unit -v --tb=short
cd ..
```

#### 5) Start frontend + backend via nginx dev script

```bash
./run_dev_nginx_both.bash
```

This starts nginx and the backend in dev mode. Keep it running in one terminal.

#### 6) Run tests (without Docker)

In another terminal from repo root:

```bash
# Backend unit tests
./test_backend_unit.sh

# Backend integration tests (requires running services)
./test_backend_integration.sh
```

For E2E tests, install frontend test dependencies once:

```bash
cd frontend
npm install
npx playwright install --with-deps chromium
cd ..

# Then run E2E tests from repo root
./test_e2e.sh
```

### Local Development With Docker Compose

Use this when you want a reproducible dev environment without installing most runtime dependencies on the host.

The Docker setup is development-oriented, not production-oriented:

- Backend source is mounted from `./backend`.
- Frontend source is mounted from `./frontend/src`.
- Backend runs in reload mode.
- Frontend is served by nginx and proxied to backend under `/ar_backend/`.

#### 1) Start the Docker dev stack

```bash
./run_dev_docker_both.bash
```

Equivalent manual command:

```bash
docker compose -f docker-compose.dev.yml up --build
```

#### 2) Stop the stack

```bash
docker compose -f docker-compose.dev.yml down
```

If you also want to remove volumes (including PostgreSQL data):

```bash
docker compose -f docker-compose.dev.yml down -v
```

#### 3) Run tests with Docker

Start the stack first (detached mode recommended for test runs):

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

Then run test scripts from repo root:

```bash
# Backend unit tests in Docker
./test_docker_backend_unit.sh

# Backend integration tests in Docker
./test_docker_backend_integration.sh

# Combined backend Docker test run (unit + integration)
./test_docker.sh

# Frontend E2E tests in Docker (Playwright container)
./test_docker_e2e.sh
```

## Author, License and Citing


The Audio Rating software was written by Tim Schäfer at the [Department of Cognitive Neuropsychology, Max-Planck Institute for Empirical Aesthetics, Frankfurt am Main, Germany](https://www.aesthetics.mpg.de/en/research/department-of-cognitive-neuropsychology.html).

The waveform visualization is powered by [wavesurfer.js](https://wavesurfer.xyz/).

Both wavesurfer.js and this software are licensed under the very permissive [3-clause BSD license](./LICENSE).

There is no academic paper on Audio Rating yet, but this software has a [DOI](https://doi.org/10.5281/zenodo.19595116) and is fully citeable. Please see the [CITATION.cff file](./CITATION.cff) for full information on how to properly cite Audio Rating in academic work.





