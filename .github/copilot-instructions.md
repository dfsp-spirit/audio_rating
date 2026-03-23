This is the Audiorating (AR) web app for music aesthetics research. It allows users to play an audio file, see the audio waveform and navigate through the audio content, and assign ratings to the sections of the audio. The user can create sections, and assign a discrete rating to each section. The widget supports several rating dimensions, so that users can rate, for example, valence, arousal, and enjoyment. The app includes a backend server for data collection and an admin interface for data management and export.

## Repo structure

The repo is organized as follows:

* `frontend/`: this directory contains the frontend code, which is a pure JavaScript app (no frameworks, no build required, no npm, no react, no vite, nothing).
* `backend/`: this directory contains the backend code, which is a Python/FastAPI app for the collection of music aesthetics data (ratings) from participants in online studies.
* `database/`: this directory contains scripts to create the database for the backend.


## General overview of the app architecture and code structure

The backend is implemented as a Python package that can be found in directly in this repo (see `backend/pyproject.toml` file). The main backend code is in the `backend/src/audiorating-backend` directory. The backend is built with FastAPI, and it uses SQLAlchemy and SQLModels for database access to a PostgreSQL dataase. There are scripts to create the database in the `database/` directory in the repo root. The backend serves a REST API that the frontend can use to get and save data. The backend does not serve the frontend files in production, they are served via nginx. The only thing the backend serves in production is the REST API and the admin interface, which is implemented using FastAPI templates. Access to the backend is via an nginx reverse proxy, which also serves the frontend files. The backend is designed to be run in a WSGI server, e.g., uvicorn in development and Gunicorn in production.

A pure JavaScript frontend for this app can be found at `frontend/src`.

## App usage and workflow from user perspective:

Users of the frontend see an instructions page for the study that typically explains the purpose of data collection and gives a quick introduction in how to use the audio rating tool. When they click next, this page is followed by the data collection page, the main page of the app. On the data collection page, users can select different songs, and for each song, they can play the audio, see the waveform for easy navigation in the song, and assign ratings to the sections of the audio. The user can create sections at will, and assign a discrete rating to each section. The widget supports several rating dimensions, so that users can rate, for example, valence, arousal, and enjoyment. When users have filled out all timelines for one day, they can click a button to finish the study. The app will save the data to the backend after each day.

## Frontend configuration

The frontend is NOT a single-page application (SPA), and it does not require or use any build system. There are npm files in `frontend/`, but they are only needed for the frontend E2E tests.


The frontend settings, the most important one of which is the backend API URL, are defined in the `frontend/src/settings/ar_settings.js` file. In production, the frontend will be served via nginx, and the backend API will be available at a nested path on the same domain, so the backend API URL in the frontend config file should be set to this nested path (e.g., `/api`), and the backend should be configured to support this via the FastAPI `root_path` setting.


## Study layer and study setup

The app can support several studies at once, defined in file `src/settings/studies_config.json`. Each study can be open to everyone (e.g., for sending invitation to a mailing list), or only to listed participants who need to know their ID or invitation link including this ID. For each study, a separate list of songs and rating dimensions can be defined. The frontend gets the list of studies and the activities for each study from the backend via the REST API, and it shows only the relevant information to users based on their ID and the study they are participating in.

Note that users do not explicitly login: they get an invitation link that includes a long ID (random string) that identifies them, and they can use this link to access the app and fill out their data. The backend identifies users based on this ID, and it does not require any other login information. This is to make it as easy as possible for users to access the app and fill out their data, without having to create an account or remember a password. If a user arrives at the frontend without a valid ID, they will be assigned a random ID, which is fine and valid for an open study, but they will not be able to access the app if the study is closed (i.e., only open to listed participants).

## Study Setup

Scientists can provide a `studies_config.json` file and the audio files to define a study. When the backend is started in scans the `studies_config.json` file and creates the studies in the database, if no study with that name exists yet. However, if a study with that name exists, no further action is taken (i.e., if the config file lists information for that study that differs from the current database contents, the study in the database is not changed, as this would require complex database migration that cannot be done automatically in general). Scientists can also use the admin interface to change some properties of a study, like add a new user to a closed study. They can of course not make changes that would require adapting the database schema in the admin interface.

## Admin Interface

The admin interface is generated by FastAPI templates, and it is only accessible to users with admin privileges. The admin interface allows scientists to view and manage the studies, activities, and user data. Scientists can also use the admin interface to export the collected data for analysis. The admin interface is protected by a login (HTTP basic auth user and password, in combination with HTTPS), and only users with admin privileges can access it. The admin user is defined in the backend config file.

## Backend configuration

The backend is configured via en `.env` file, which is read by the backend at startup. The config file includes settings for the database connection, the admin user, and other settings. The file is expected to be in the root of the backend directory, and it should not be committed to version control, as it may contain sensitive information (e.g., database password). An example config file can be found at `backend/.env.example`.


In production, the frontend and backend may be run on different servers and at a nested path on a domain, so we need to make sure that the backend can be configured to support this, via the FastAPI `root_path` setting.

### Backend build system

The backend uses `uv`, and one should use it for all commands or manually activate the .venv it creates first. E.g., the recommended way to run the unit tests would be `cd backend && uv run pytest`. An alternative is `cd backend && source .venv/bin/activate && python -m pytest`. But `uv` is the way to go. So to build the backend, do `cd backend && uv run build`.


## Development scripts

There are scripts to start the backend and frontend in development mode, which can be found in the repo root directory. The recommended way is to install nginx on your development machine and the use the `run_dev_nginx.sh` script to start nginx with the correct configuration for the frontend and backend. This way, you can access the frontend and backend at the same paths as in production (with nginx root_path), which makes the development environment more similar to production and prevents path errors in links in templates, etc. With this script, the frontend is at `http://localhost:3000/rate/study.html`, and the backend is at `http://localhost:3000/ar_backend/` unless you change the nginx template config file shipped in this repo. The dev script runs nginx as your user, so you only need root access once to install nginx.

The `run_backend_dev_minimal.sh` and `run_frontend_dev_minimal.sh` scripts can be used to start the backend and frontend in development mode without nginx (using Python's built-in webserver) directly at localhost:3000, and the backend directly at localhost:8000, but this setup is not recommended, as it does not reflect the production setup well and may lead to path errors in links in templates, etc. The integration and e2e tests will also not work this way.

### Testing

Please see the `test_*` scripts in the repo for more information on how to run the tests. The tests assume that services are running.

There is also a CI setup using GitHub actions, which runs the tests automatically on each push to the repo. The CI setup can be found in the `.github/workflows/` directory in the repo.

## Security

Note that the backend will run on a public server on the internet, so security is very important. Everything, especially the backend, should be designed with security in mind, e.g., by validating all input data, using secure headers, and following best practices for web application security.
