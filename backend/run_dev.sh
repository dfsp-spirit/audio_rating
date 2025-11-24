#!/bin/bash
#

uv run uvicorn audiorating_backend.api:app --reload --host 127.0.0.1 --port 8000
