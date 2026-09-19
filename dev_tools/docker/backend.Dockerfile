FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --no-cache-dir uv

WORKDIR /workspace/backend

CMD ["sh", "-lc", "uv sync --dev && uv run uvicorn audiorating_backend.api:app --reload --host 0.0.0.0 --port 8000"]
